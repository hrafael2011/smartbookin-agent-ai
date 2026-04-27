"""
Contexto del cliente para el NLU: una sola fuente de verdad (citas + nombre + hints).
"""
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services import db_service
from app.utils.name_usage_hint import name_usage_hint

_ACTIVE_STATUSES = frozenset({"P", "C", "pending", "confirmed"})
_CANCELLED = frozenset({"A", "a", "canceled", "cancelled"})


def _parse_start_at(a: Dict[str, Any]) -> datetime:
    s = a.get("start_at")
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=None)
    if not s:
        return datetime.min
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


async def _build_history_hints_block(customer_id: int) -> str:
    """
    Resumen de historial para sugerir servicio/hora sin inventar datos nuevos.
    """
    all_apps = await db_service.get_customer_appointments(customer_id, upcoming=False)
    if not all_apps:
        return ""

    relevant = [a for a in all_apps if str(a.get("status", "")).strip().upper() not in _CANCELLED]
    if not relevant:
        relevant = list(all_apps)

    sorted_desc = sorted(relevant, key=_parse_start_at, reverse=True)
    last = sorted_desc[0]
    last_name = (last.get("service_name") or "—").strip()
    last_when = format_appointment_start_display(last.get("start_at"))

    names = [(a.get("service_name") or "").strip() for a in relevant if (a.get("service_name") or "").strip()]
    if not names:
        return ""

    cnt = Counter(names)
    habitual_name, habitual_n = cnt.most_common(1)[0]

    lines = [
        "HISTORIAL (datos reales; usá solo esto para sugerencias, no inventes otros):",
        f"- Última reserva en historial: {last_name} ({last_when})",
    ]
    if habitual_n >= 2:
        lines.append(f"- Servicio más repetido en historial: {habitual_name} ({habitual_n} veces)")
    pref = await db_service.get_customer_preferred_time_hhmm(customer_id)
    if pref:
        lines.append(f"- Hora más habitual en reservas previas (aprox.): {pref}")

    return "\n".join(lines) + "\n"


def format_appointment_start_display(start_at: Any) -> str:
    """start_at en API es ISO string o datetime; formato legible para el prompt."""
    if isinstance(start_at, datetime):
        return start_at.strftime("%d/%m/%Y %H:%M")
    s = str(start_at or "").strip()
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return s


async def build_customer_context_for_nlu(
    customer_id: Optional[int],
    customer_name: str,
    recent_messages: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Texto inyectado en el system prompt del NLU: nombre, citas activas, hint de uso del nombre.
    Devuelve cadena vacía si no hay cliente identificado.
    """
    if not customer_id:
        return ""
    display_name = (customer_name or "").strip() or "Cliente"
    appointments = await db_service.get_customer_appointments(customer_id)
    active_apps = [a for a in appointments if a.get("status") in _ACTIVE_STATUSES]

    parts: List[str] = [f"Nombre: {display_name}\n"]
    if active_apps:
        parts.append("Citas activas:\n")
        for a in active_apps:
            parts.append(
                f"- {a['service_name']} el {format_appointment_start_display(a.get('start_at'))}\n"
            )
    else:
        parts.append("No tiene citas programadas actualmente.")
    text = "".join(parts)

    history = await _build_history_hints_block(customer_id)
    if history:
        text += "\n" + history

    text += name_usage_hint(display_name, recent_messages or [])
    return text
