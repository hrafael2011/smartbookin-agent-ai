"""
Renderer de BotReply → payload interactivo de WhatsApp (decisión #7: nunca
menús numerados ni texto libre para decisiones; el usuario toca botones o listas).

Reglas de mapeo (presupuesto Meta: reply ≤3 botones / list ≤10 filas):
    - 0 opciones propias (solo footer nav_*)  → texto puro
    - 1..3 opciones                           → reply buttons (sin footer)
    - 4..10 opciones                          → list message (con navegación si cabe)
    - >10 opciones                            → primeras 7 + fila de paginación
                                                (slots_page_<n> del teclado si existe)
Los ids son el callback_data SIN token de pantalla (el token es de Telegram);
los títulos se recortan a los límites de Meta (20 botones / 24 filas).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.core.response_builder import BotReply
from app.utils.telegram_ui import parse_inline_callback, split_callback_token

logger = logging.getLogger(__name__)

_ES_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Títulos de sección por namespace (resto → "Opciones"; time_/day_ tienen título dinámico).
_SECTION_TITLES = {
    "service": "Servicios",
    "menu": "Opciones",
    "month": "Meses",
    "week": "Semanas",
    "cancel_appt": "Tus citas",
    "modify_appt": "Tus citas",
    "confirm": "Confirmación",
    "cancel_confirm": "Confirmación",
    "resume": "Confirmación",
}


@dataclass
class WhatsAppRender:
    """Render listo para enviar: kind text|button|list + payload parcial."""

    kind: str  # "text" | "button" | "list"
    text: str
    buttons: List[Dict[str, str]] = field(default_factory=list)  # kind="button"
    sections: List[Dict] = field(default_factory=list)  # kind="list"
    dropped: int = 0  # opciones descartadas por el presupuesto de Meta


def render_bot_reply(reply: BotReply, *, now: Optional[datetime] = None) -> WhatsAppRender:
    """Traduce un BotReply (texto + teclado Telegram) a un render de WhatsApp."""
    keyboard = reply.keyboard or []
    parsed = [
        (btn, parse_inline_callback(btn["callback_data"]))
        for row in keyboard
        for btn in row
    ]
    nav = [btn for btn, p in parsed if p and p["ns"] == "nav"]
    pages = [btn for btn, p in parsed if p and p["ns"] == "slots_page"]
    own = [btn for btn, p in parsed if p and p["ns"] not in ("nav", "slots_page")]
    unknown = sum(1 for _, p in parsed if p is None)

    text = reply.text_plain or strip_html(str(reply)) if not own else strip_html(str(reply))

    if not own:
        return WhatsAppRender(kind="text", text=text, dropped=unknown)

    # Reply buttons (≤3): decisiones; la paginación solo si cabe en el cupo.
    if len(own) <= 3 and not pages:
        return WhatsAppRender(
            kind="button",
            text=text,
            buttons=[_reply_button(b) for b in own],
            dropped=unknown,
        )
    if len(own) <= 3 and pages:
        # Página con pocos slots pero con "Ver más": lista para conservar la paginación.
        rows = [*own, _next_page_button(pages)]
        sections = _group_sections(rows, now)
        dropped = unknown + len(pages) - 1
        return _list_render(text, sections, nav, dropped)

    # List message: presupuesto de 10 filas.
    if len(own) <= 10:
        rows = own
        dropped = unknown
    else:
        rows = own[:7]
        dropped = unknown + (len(own) - 7)
        nxt = _next_page_button(pages)
        if nxt:
            rows.append(nxt)
            dropped += len(pages) - 1

    sections = _group_sections(rows, now)
    return _list_render(text, sections, nav, dropped)


def _list_render(text: str, sections: List[Dict], nav: List[Dict], dropped: int) -> WhatsAppRender:
    """Lista final: agrega la sección de navegación solo si cabe (≤10 filas)."""
    rows_used = sum(len(s["rows"]) for s in sections)
    if nav and rows_used + len(nav) <= 10:
        sections.append({"title": "Navegación", "rows": [_list_row(b) for b in nav]})
    else:
        dropped += len(nav)
    if dropped:
        logger.debug("wa_render dropped=%s kind=list", dropped)
    return WhatsAppRender(kind="list", text=text, sections=sections, dropped=dropped)


def strip_html(text: str) -> str:
    """Convierte HTML de Telegram a formato WhatsApp: <b>→*, <i>→_, resto se elimina."""
    t = re.sub(r"<b>(.*?)</b>", r"*\1*", text or "", flags=re.DOTALL)
    t = re.sub(r"<i>(.*?)</i>", r"_\1_", t, flags=re.DOTALL)
    return re.sub(r"<[^>]+>", "", t)


def _clip(text: str, limit: int) -> str:
    """Trunca a `limit` code points, dejando el último para «…»."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _base_id(btn: Dict[str, str]) -> str:
    """callback_data sin token de pantalla (el token es de Telegram)."""
    return split_callback_token(btn["callback_data"])[0]


def _reply_button(btn: Dict[str, str]) -> Dict[str, str]:
    return {"id": _base_id(btn), "title": _clip(btn.get("text", ""), 20)}


def _list_row(btn: Dict[str, str]) -> Dict[str, str]:
    return {"id": _base_id(btn), "title": _clip(btn.get("text", ""), 24)}


def _next_page_button(pages: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """El botón de paginación de mayor página (siguiente), si existe."""
    if not pages:
        return None
    return max(pages, key=lambda b: _page_number(b))


def _page_number(btn: Dict[str, str]) -> int:
    p = parse_inline_callback(btn["callback_data"])
    try:
        return int(p["value"])
    except (TypeError, ValueError):
        return 0


def _group_sections(rows: List[Dict[str, str]], now: Optional[datetime]) -> List[Dict]:
    """Agrupa filas por namespace → secciones (time_ y day_ con títulos dinámicos)."""
    groups: Dict[tuple, Dict] = {}
    for btn in rows:
        p = parse_inline_callback(btn["callback_data"])
        if not p:
            continue
        ns = p["ns"]
        if ns == "time":
            title = f"Horarios · {_fecha_corta(p['value'][0])}"
        elif ns == "day":
            title = _semana_title(p["value"], now)
        else:
            title = _SECTION_TITLES.get(ns, "Opciones")
        key = (ns, title)
        groups.setdefault(key, {"title": title, "rows": []})["rows"].append(
            _list_row(btn)
        )
    return list(groups.values())


def _fecha_corta(iso: str) -> str:
    try:
        d = date_type.fromisoformat(iso)
        return f"{d.day} {_ES_MESES[d.month - 1]}"
    except ValueError:
        return iso


def _semana_title(iso: str, now: Optional[datetime]) -> str:
    try:
        d = date_type.fromisoformat(iso)
    except ValueError:
        return "Opciones"
    if now is None:
        now = datetime.now()
    this_monday = now.date() - timedelta(days=now.date().weekday())
    next_monday = this_monday + timedelta(days=7)
    if this_monday <= d < next_monday:
        return "Esta semana"
    if next_monday <= d < next_monday + timedelta(days=7):
        return "Próxima semana"
    return "Otras fechas"
