"""Builders de teclados inline (Telegram) y convención de callback_data.

Convención de callback_data (compartible 1:1 con WhatsApp Business API):

    service_<id>                     Selección de servicio
    day_<YYYY-MM-DD>                 Selección de día
    time_<YYYY-MM-DD>_<HH:MM>        Selección de horario (HH:MM en 24h)
    slots_page_<n>                   Paginación de la grilla de horarios
    month_<n> / week_<n>             Calendario: mes / semana
    month_browse                    Ver otros meses desde la semana actual
    menu_agendar | menu_ver_citas | menu_cambiar | menu_cancelar | menu_horarios
    nav_back | nav_menu | nav_exit   Footer centralizado de navegación
    confirm_yes | confirm_no         Confirmación de cita
    cancel_appt_<id>                 Cita a cancelar
    cancel_confirm_yes | cancel_confirm_no
    modify_appt_<id>                 Cita a modificar
    resume_yes | resume_no           Continuar / cerrar sesión vencida

Toda pantalla del flujo concatena build_nav_footer() al final de su teclado
(helper with_footer). Única excepción: el menú principal (pantalla raíz).
"""
from __future__ import annotations

import re
from datetime import date as date_type
from datetime import datetime
from typing import Dict, List, Optional

from app.config import config
from app.core.response_builder import BotReply, KeyboardRow
from app.utils.conversation_routing import guided_menu

_WEEKDAYS_ABBR = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

_GRID_COLUMNS = 3
_GRID_PAGE_SIZE = 12  # 4 filas × 3 columnas


# ── Footer centralizado ───────────────────────────────────────────────────────

def build_nav_footer() -> List[Dict[str, str]]:
    """Fila única de navegación que debe cerrar TODO teclado del flujo."""
    return [
        {"text": "🔙 Volver", "callback_data": "nav_back"},
        {"text": "🏠 Menú", "callback_data": "nav_menu"},
        {"text": "❌ Salir", "callback_data": "nav_exit"},
    ]


def with_footer(rows: KeyboardRow) -> KeyboardRow:
    """Concatena el footer de navegación al final del teclado propio."""
    return [*rows, build_nav_footer()]


# ── Menú principal ────────────────────────────────────────────────────────────

def main_menu_keyboard() -> KeyboardRow:
    return [
        [{"text": "📅 Agendar cita", "callback_data": "menu_agendar"}],
        [{"text": "📋 Ver mis citas", "callback_data": "menu_ver_citas"}],
        [{"text": "✏️ Cambiar cita", "callback_data": "menu_cambiar"}],
        [{"text": "❌ Cancelar cita", "callback_data": "menu_cancelar"}],
        [{"text": "📍 Horarios y ubicación", "callback_data": "menu_horarios"}],
    ]


def guided_menu_short(customer_name: str = "", *, returning: bool = False) -> str:
    """Texto del menú SIN numeración (para pantallas con teclado de botones)."""
    if returning and customer_name:
        lead = f"¡Bienvenido de nuevo, <b>{customer_name}</b>! 👋"
    elif customer_name:
        lead = f"¡Hola, <b>{customer_name}</b>! 👋"
    else:
        lead = "¡Hola! 👋"
    parts = [f"{lead}\n\n", "Elegí una opción:"]
    if config.ai_enabled:
        parts.append('\n\nTambién podés escribir tu pedido directo (ej. "quiero cita mañana 10am").')
    return "".join(parts)


def main_menu_reply(prefix: str = "", customer_name: str = "") -> BotReply:
    """Mensaje del menú principal: texto corto + teclado; text_plain numerado para canales sin teclado."""
    text = guided_menu_short(customer_name)
    if prefix:
        text = f"{prefix}\n\n{text}"
    plain = guided_menu(customer_name)
    if prefix:
        plain = f"{prefix}\n\n{plain}"
    return BotReply(text, keyboard=main_menu_keyboard(), text_plain=plain)


def guided_menu_reply(customer_name: str = "") -> BotReply:
    """El menú principal como BotReply con su teclado (pantalla raíz, sin footer)."""
    return main_menu_reply(customer_name=customer_name)


# ── Servicios ─────────────────────────────────────────────────────────────────

def service_buttons(services: List[Dict]) -> KeyboardRow:
    """Un botón por servicio: `service_<id>`, dos por fila."""
    rows: KeyboardRow = []
    for i in range(0, len(services), 2):
        rows.append(
            [
                {"text": str(services[j]["name"]), "callback_data": f"service_{services[j]['id']}"}
                for j in range(i, min(i + 2, len(services)))
            ]
        )
    return rows


# ── Días ──────────────────────────────────────────────────────────────────────

def day_buttons(days: List[Dict]) -> KeyboardRow:
    """Un botón por día disponible: `day_<YYYY-MM-DD>`."""
    return [
        [{"text": str(d.get("label") or d["date"]), "callback_data": f"day_{d['date']}"}]
        for d in days
    ]


# ── Grilla de horarios (paginada) ─────────────────────────────────────────────

def paginate_slots(
    slots: List[Dict], page: int, page_size: int = _GRID_PAGE_SIZE
) -> Dict:
    total = len(slots)
    total_pages = max(1, -(-total // page_size))
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    return {
        "slots": slots[start:end],
        "page": page,
        "total_pages": total_pages,
        "has_prev": page > 0,
        "has_next": page < total_pages - 1,
    }


def slot_by_hhmm(slots: List[Dict], hhmm: str) -> Optional[Dict]:
    """Primer slot cuyo start_datetime coincide con ``HH:MM`` (formato 24h del callback)."""
    for slot in slots:
        if _slot_hhmm(slot) == hhmm:
            return slot
    return None


def _slot_hhmm(slot: Dict) -> str:
    raw = str(slot.get("start_datetime") or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return str(slot.get("start_time") or "")


def time_grid_buttons(
    slots: List[Dict],
    date_str: str,
    page: int = 0,
    page_size: int = _GRID_PAGE_SIZE,
) -> KeyboardRow:
    """Grilla de 3 columnas `time_<YYYY-MM-DD>_<HH:MM>` con paginación.

    La fila de paginación (◀ Antes / Después ▶) solo aparece cuando hay más
    de una página; el footer de navegación va SIEMPRE debajo (with_footer).
    """
    page_info = paginate_slots(slots, page=page, page_size=page_size)
    rows: KeyboardRow = []
    for i in range(0, len(page_info["slots"]), _GRID_COLUMNS):
        rows.append(
            [
                {
                    "text": str(slot.get("start_time") or _slot_hhmm(slot)),
                    "callback_data": f"time_{date_str}_{_slot_hhmm(slot)}",
                }
                for slot in page_info["slots"][i : i + _GRID_COLUMNS]
            ]
        )
    nav_row = []
    if page_info["has_prev"]:
        nav_row.append({"text": "◀ Antes", "callback_data": f"slots_page_{page_info['page'] - 1}"})
    if page_info["has_next"]:
        nav_row.append({"text": "Después ▶", "callback_data": f"slots_page_{page_info['page'] + 1}"})
    if nav_row:
        rows.append(nav_row)
    return rows


# ── Citas (cancelar / modificar) ──────────────────────────────────────────────

def short_appointment_label(appt: Dict) -> str:
    """'Corte · vie 28, 9:00 AM' — etiqueta corta para botones de cita."""
    service = appt.get("service_name") or "Servicio"
    try:
        start = datetime.fromisoformat(str(appt.get("start_at") or "").replace("Z", "+00:00"))
        wd = _WEEKDAYS_ABBR[start.weekday()]
        time_txt = start.strftime("%I:%M %p").lstrip("0")
        return f"{service} · {wd} {start.day}, {time_txt}"
    except ValueError:
        return service


def appointment_buttons(appointments: List[Dict], prefix: str) -> KeyboardRow:
    """Una cita real por botón: `cancel_appt_<id>` / `modify_appt_<id>`."""
    return [
        [{"text": short_appointment_label(a), "callback_data": f"{prefix}_{a['id']}"}]
        for a in appointments
    ]


# ── Confirmaciones ────────────────────────────────────────────────────────────

def confirm_booking_buttons() -> KeyboardRow:
    return [
        [
            {"text": "✅ Confirmar", "callback_data": "confirm_yes"},
            {"text": "🔁 Ver otro horario", "callback_data": "confirm_no"},
        ]
    ]


def cancel_confirm_buttons() -> KeyboardRow:
    return [
        [
            {"text": "✅ Sí, cancelar", "callback_data": "cancel_confirm_yes"},
            {"text": "❌ No, mantener", "callback_data": "cancel_confirm_no"},
        ]
    ]


def resume_buttons() -> KeyboardRow:
    return [
        [
            {"text": "✅ Sí, continuar", "callback_data": "resume_yes"},
            {"text": "❌ No, cerrar", "callback_data": "resume_no"},
        ]
    ]


# ── Calendario: meses y semanas ───────────────────────────────────────────────

def month_buttons(months: List[Dict]) -> KeyboardRow:
    return [[{"text": str(m["label"]), "callback_data": f"month_{m['index']}"}] for m in months]


def week_buttons(weeks: List[Dict]) -> KeyboardRow:
    return [
        [
            {
                "text": f"{w['label']} ({w['day_count']} días)",
                "callback_data": f"week_{w['index']}",
            }
        ]
        for w in weeks
    ]


# ── Parser de callback_data ───────────────────────────────────────────────────

_CALLBACK_PATTERNS: List[tuple] = [
    ("service", re.compile(r"^service_(\d+)$")),
    ("day", re.compile(r"^day_(\d{4}-\d{2}-\d{2})$")),
    ("time", re.compile(r"^time_(\d{4}-\d{2}-\d{2})_(\d{2}:\d{2})$")),
    ("slots_page", re.compile(r"^slots_page_(\d+)$")),
    ("month", re.compile(r"^month_(\d+)$")),
    ("month_browse", re.compile(r"^(month_browse)$")),
    ("week", re.compile(r"^week_(\d+)$")),
    ("cancel_appt", re.compile(r"^cancel_appt_(\d+)$")),
    ("modify_appt", re.compile(r"^modify_appt_(\d+)$")),
    ("menu", re.compile(r"^menu_(agendar|ver_citas|cambiar|cancelar|horarios)$")),
    ("nav", re.compile(r"^nav_(back|menu|exit)$")),
    ("confirm", re.compile(r"^confirm_(yes|no)$")),
    ("cancel_confirm", re.compile(r"^cancel_confirm_(yes|no)$")),
    ("resume", re.compile(r"^resume_(yes|no)$")),
]


def _valid_iso_date(value: str) -> bool:
    try:
        date_type.fromisoformat(value)
        return True
    except ValueError:
        return False


def _valid_hhmm(value: str) -> bool:
    try:
        hour, minute = (int(part) for part in value.split(":"))
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except (ValueError, TypeError):
        return False


def parse_inline_callback(text: str) -> Optional[Dict]:
    """Convierte un callback_data en ``{"ns": ..., "value": ...}`` o None.

    ``value`` es el string capturado, o tupla si el patrón tiene varios grupos.
    Los payloads de fecha/hora se validan semánticamente (día 2026-13-45 o
    hora 99:99 no son callbacks válidos).
    """
    t = str(text or "")
    for ns, pattern in _CALLBACK_PATTERNS:
        m = pattern.match(t)
        if not m:
            continue
        groups = m.groups()
        value = groups[0] if len(groups) == 1 else tuple(groups)
        if ns == "day" and not _valid_iso_date(str(value)):
            continue
        if ns == "time" and (
            not _valid_iso_date(str(value[0])) or not _valid_hhmm(str(value[1]))
        ):
            continue
        return {"ns": ns, "value": value}
    return None
