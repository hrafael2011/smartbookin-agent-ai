"""Deterministic routing for the owner-only Telegram command channel."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.services.conversation_manager import conversation_manager
from app.services.owner_mutations import (
    owner_block_timeslot,
    owner_cancel_appointment,
    owner_complete_appointment,
    owner_reschedule_appointment,
)
from app.services.owner_read_models import (
    _resolve_tz,
    format_agenda_response,
    format_appointment_detail,
    format_metrics_response,
    get_owner_daily_metrics,
    list_owner_agenda,
    list_owner_upcoming,
    local_today,
)
from app.services import db_service

logger = logging.getLogger(__name__)

OWNER_SESSION_TIMEOUT_SECONDS = 30 * 60
OWNER_TIMEZONE = ZoneInfo("America/Santo_Domingo")

_MAIN_MENU_WORDS = {"0", "menu", "menú", "inicio", "menu principal", "menú principal", "/start"}
_BACK_WORDS = {"9", "volver", "atras", "atrás"}
_EXIT_WORDS = {"x", "salir", "terminar", "cerrar", "cerrar sesion", "cerrar sesión"}
_YES_WORDS = {"si", "sí", "yes", "confirmo", "confirmar", "dale", "ok", "claro", "adelante", "procede", "proceder"}
_NO_WORDS = {"no", "nope", "cancelar", "mejor no", "olvidalo", "olvídalo"}

_OWNER_COMMAND_WORDS = (
    "agenda",
    "citas de hoy",
    "citas manana",
    "citas mañana",
    "proximas citas",
    "próximas citas",
    "metricas",
    "métricas",
    "ganancias",
    "ingresos",
    "notificaciones",
    "panel",
    "dueno",
    "dueño",
    "bloquear",
    "bloqueo",
)

# States where a free-text or numeric reply is part of an active owner flow
_FLOW_STATES = {
    "owner_cancel_confirm",
    "owner_complete_confirm",
    "owner_reschedule_ask_date",
    "owner_reschedule_slots",
    "owner_reschedule_confirm",
    "owner_block_ask_date",
    "owner_block_ask_start",
    "owner_block_ask_end",
    "owner_block_confirm",
}


@dataclass(frozen=True)
class OwnerRouteDecision:
    kind: str
    option: Optional[str] = None
    reason: str = ""
    uses_ai: bool = False


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def owner_user_key(telegram_user_id: str) -> str:
    return f"owner:tg:{telegram_user_id}"


def owner_menu(business_name: str) -> str:
    return (
        f"Panel rápido - <b>{business_name}</b>\n\n"
        "1) Agenda de hoy\n"
        "2) Agenda de mañana\n"
        "3) Próximas citas\n"
        "4) Métricas de hoy\n"
        "5) Notificaciones\n"
        "6) Bloquear horario\n\n"
        "9) Volver\n"
        "0) Menú principal\n"
        "X) Salir"
    )


def looks_like_owner_command(message_text: str) -> bool:
    t = _norm(message_text)
    if not t:
        return False
    if t in _MAIN_MENU_WORDS or t in _BACK_WORDS or t in _EXIT_WORDS:
        return True
    return any(word in t for word in _OWNER_COMMAND_WORDS)


def _is_active_context(context: dict) -> bool:
    return (context.get("state") or "idle") != "idle"


def _is_expired_owner_session(context: dict) -> bool:
    if not _is_active_context(context):
        return False
    raw = context.get("last_activity")
    if not raw:
        return False
    try:
        last = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() > OWNER_SESSION_TIMEOUT_SECONDS


def route_owner_command(message_text: str, context: dict) -> OwnerRouteDecision:
    t = _norm(message_text)

    if _is_expired_owner_session(context):
        return OwnerRouteDecision("expired_session", reason="owner_session_timeout")

    if t in _MAIN_MENU_WORDS:
        return OwnerRouteDecision("show_menu", reason="main_menu")
    if t in _BACK_WORDS:
        return OwnerRouteDecision("go_back", reason="back")
    if t in _EXIT_WORDS:
        return OwnerRouteDecision("exit_session", reason="exit")

    current_state = context.get("state") or "idle"

    # Action inputs inside active flows — pass raw text to executor
    if current_state in _FLOW_STATES:
        return OwnerRouteDecision("flow_input", option=t, reason=f"flow_{current_state}")

    # Actions from appointment detail view
    if current_state == "owner_appointment_detail":
        if t in {"c", "cancelar"}:
            return OwnerRouteDecision("action_cancel", reason="cancel_from_detail")
        if t in {"m", "completar", "completada", "marcar completada", "marcar como completada"}:
            return OwnerRouteDecision("action_complete", reason="complete_from_detail")
        if t in {"r", "reagendar", "mover", "cambiar hora", "cambiar fecha"}:
            return OwnerRouteDecision("action_reschedule", reason="reschedule_from_detail")
        if t.isdigit():
            return OwnerRouteDecision("agenda_detail", option=t, reason="agenda_detail")

    # Agenda list — numeric selects a detail
    if current_state == "owner_agenda_list" and t.isdigit():
        return OwnerRouteDecision("agenda_detail", option=t, reason="agenda_detail")

    if t in {"1", "2", "3", "4", "5", "6"}:
        return OwnerRouteDecision("menu_option", option=t, reason=f"option_{t}")

    # Natural language shortcuts
    if "hoy" in t and ("agenda" in t or "cita" in t):
        return OwnerRouteDecision("menu_option", option="1", reason="today_agenda_shortcut")
    if ("mañana" in t or "manana" in t) and ("agenda" in t or "cita" in t):
        return OwnerRouteDecision("menu_option", option="2", reason="tomorrow_agenda_shortcut")
    if "proxima" in t or "próxima" in t or "proximas" in t or "próximas" in t:
        return OwnerRouteDecision("menu_option", option="3", reason="upcoming_shortcut")
    if any(word in t for word in ("metricas", "métricas", "ganancias", "ingresos")):
        return OwnerRouteDecision("menu_option", option="4", reason="metrics_shortcut")
    if "notificacion" in t or "notificación" in t:
        return OwnerRouteDecision("menu_option", option="5", reason="notifications_shortcut")
    if "bloquear" in t or "bloqueo" in t or "bloquear horario" in t:
        return OwnerRouteDecision("menu_option", option="6", reason="block_shortcut")

    return OwnerRouteDecision("show_menu", reason="fallback")


# ── Context helpers ────────────────────────────────────────────────────────────

async def _clear_to_idle(business_id: int, user_key: str) -> None:
    await conversation_manager.update_context(
        business_id, user_key,
        {"current_intent": None, "pending_data": {}, "state": "idle"},
    )


async def _set_owner_idle(business_id: int, user_key: str) -> None:
    await conversation_manager.update_context(
        business_id, user_key,
        {"current_intent": "owner_command", "pending_data": {}, "state": "idle"},
    )


async def _set_state(business_id: int, user_key: str, state: str, pending_data: dict) -> None:
    await conversation_manager.update_context(
        business_id, user_key,
        {"current_intent": "owner_command", "pending_data": pending_data, "state": state},
    )


async def _set_owner_agenda_list(
    business_id: int, user_key: str, items: list[dict], *, list_kind: str
) -> None:
    await _set_state(business_id, user_key, "owner_agenda_list", {"owner_agenda": items, "owner_agenda_kind": list_kind})


# ── Format helpers ─────────────────────────────────────────────────────────────

def _agenda_title(list_kind: str) -> str:
    today = local_today()
    if list_kind == "today":
        return f"Agenda de hoy ({today.isoformat()})"
    if list_kind == "tomorrow":
        return f"Agenda de mañana ({(today + timedelta(days=1)).isoformat()})"
    return "Próximas citas"


def _is_affirmative(t: str) -> bool:
    return t in _YES_WORDS or t.startswith("si") or t.startswith("sí")


def _is_negative(t: str) -> bool:
    return t in _NO_WORDS or t.startswith("no ")


# ── Read flows ─────────────────────────────────────────────────────────────────

async def _agenda_today(owner_id: int, business_id: int, user_key: str, tz_name: str) -> str:
    tz = _resolve_tz(tz_name)
    items = await list_owner_agenda(owner_id=owner_id, business_id=business_id, target_day=local_today(tz), tz_name=tz_name)
    await _set_owner_agenda_list(business_id, user_key, items, list_kind="today")
    return format_agenda_response(_agenda_title("today"), items)


async def _agenda_tomorrow(owner_id: int, business_id: int, user_key: str, tz_name: str) -> str:
    tz = _resolve_tz(tz_name)
    day = local_today(tz) + timedelta(days=1)
    items = await list_owner_agenda(owner_id=owner_id, business_id=business_id, target_day=day, tz_name=tz_name)
    await _set_owner_agenda_list(business_id, user_key, items, list_kind="tomorrow")
    return format_agenda_response(_agenda_title("tomorrow"), items)


async def _upcoming(owner_id: int, business_id: int, user_key: str, tz_name: str) -> str:
    items = await list_owner_upcoming(owner_id=owner_id, business_id=business_id, tz_name=tz_name)
    await _set_owner_agenda_list(business_id, user_key, items, list_kind="upcoming")
    return format_agenda_response(_agenda_title("upcoming"), items)


async def _metrics_today(owner_id: int, business_id: int, user_key: str, tz_name: str) -> str:
    tz = _resolve_tz(tz_name)
    day = local_today(tz)
    metrics = await get_owner_daily_metrics(owner_id=owner_id, business_id=business_id, target_day=day, tz_name=tz_name)
    await _set_state(business_id, user_key, "owner_metrics", {})
    return format_metrics_response(f"Métricas de hoy ({day.isoformat()})", metrics)


async def _back_from_detail(business_id: int, user_key: str, context: dict) -> str:
    pending = context.get("pending_data") or {}
    items = pending.get("owner_agenda") or []
    list_kind = pending.get("owner_agenda_kind") or "upcoming"
    await _set_owner_agenda_list(business_id, user_key, items, list_kind=list_kind)
    return format_agenda_response(_agenda_title(list_kind), items)


async def _agenda_detail(business_id: int, user_key: str, context: dict, option: Optional[str]) -> str:
    items = (context.get("pending_data") or {}).get("owner_agenda") or []
    try:
        index = int(option or "0") - 1
    except ValueError:
        index = -1
    if index < 0 or index >= len(items):
        return f"Elegí un número entre 1 y {len(items)}.\n\n9) Volver\n0) Menú principal\nX) Salir"
    item = items[index]
    pending = {**(context.get("pending_data") or {}), "selected_item": item}
    await _set_state(business_id, user_key, "owner_appointment_detail", pending)
    return format_appointment_detail(item)


# ── Mutation flows ─────────────────────────────────────────────────────────────

def _selected_item(context: dict) -> Optional[dict]:
    return (context.get("pending_data") or {}).get("selected_item")


async def _start_cancel(business_id: int, user_key: str, context: dict) -> str:
    item = _selected_item(context)
    if not item:
        return "No tengo la cita seleccionada. Elegí una cita desde la agenda primero.\n\n9) Volver"
    pending = {**(context.get("pending_data") or {})}
    await _set_state(business_id, user_key, "owner_cancel_confirm", pending)
    return (
        f"¿Confirmás que querés <b>cancelar</b> la cita #{item.get('appointment_id')} "
        f"({item.get('local_time')} — {item.get('customer_name')})?\n\n"
        "Respondé <b>sí</b> para confirmar o <b>no</b> para volver."
    )


async def _confirm_cancel(business_id: int, user_key: str, context: dict, t: str, business_name: str) -> str:
    if _is_negative(t):
        await _set_state(business_id, user_key, "owner_appointment_detail", context.get("pending_data") or {})
        item = _selected_item(context)
        return format_appointment_detail(item) if item else owner_menu(business_name)

    if not _is_affirmative(t):
        return "No entendí. Respondé <b>sí</b> para cancelar o <b>no</b> para volver."

    item = _selected_item(context)
    if not item:
        await _set_owner_idle(business_id, user_key)
        return "No encontré la cita. Volvé a la agenda.\n\n" + owner_menu(business_name)

    result = await owner_cancel_appointment(item["appointment_id"], business_id)
    await _set_owner_idle(business_id, user_key)
    if result.ok:
        return f"✅ Cita #{item['appointment_id']} cancelada.\n\n" + owner_menu(business_name)
    if result.error == "not_cancellable":
        return f"Esta cita ya no se puede cancelar (estado actual no es P ni C).\n\n" + owner_menu(business_name)
    return f"No se pudo cancelar la cita. Intentá de nuevo.\n\n" + owner_menu(business_name)


async def _start_complete(business_id: int, user_key: str, context: dict) -> str:
    item = _selected_item(context)
    if not item:
        return "No tengo la cita seleccionada. Elegí una cita desde la agenda primero.\n\n9) Volver"
    pending = {**(context.get("pending_data") or {})}
    await _set_state(business_id, user_key, "owner_complete_confirm", pending)
    return (
        f"¿Confirmás que querés marcar como <b>completada</b> la cita #{item.get('appointment_id')} "
        f"({item.get('local_time')} — {item.get('customer_name')})?\n\n"
        "Respondé <b>sí</b> para confirmar o <b>no</b> para volver."
    )


async def _confirm_complete(business_id: int, user_key: str, context: dict, t: str, business_name: str) -> str:
    if _is_negative(t):
        await _set_state(business_id, user_key, "owner_appointment_detail", context.get("pending_data") or {})
        item = _selected_item(context)
        return format_appointment_detail(item) if item else owner_menu(business_name)

    if not _is_affirmative(t):
        return "No entendí. Respondé <b>sí</b> para confirmar o <b>no</b> para volver."

    item = _selected_item(context)
    if not item:
        await _set_owner_idle(business_id, user_key)
        return "No encontré la cita.\n\n" + owner_menu(business_name)

    result = await owner_complete_appointment(item["appointment_id"], business_id)
    await _set_owner_idle(business_id, user_key)
    if result.ok:
        return f"✅ Cita #{item['appointment_id']} marcada como completada.\n\n" + owner_menu(business_name)
    if result.error == "not_completable":
        return "Esta cita no se puede marcar como completada (solo se acepta desde P o C).\n\n" + owner_menu(business_name)
    return "No se pudo completar la cita. Intentá de nuevo.\n\n" + owner_menu(business_name)


async def _start_reschedule(business_id: int, user_key: str, context: dict) -> str:
    item = _selected_item(context)
    if not item:
        return "No tengo la cita seleccionada. Elegí una cita desde la agenda primero.\n\n9) Volver"
    pending = {**(context.get("pending_data") or {})}
    await _set_state(business_id, user_key, "owner_reschedule_ask_date", pending)
    return (
        f"Reagendando cita #{item.get('appointment_id')} — {item.get('customer_name')}.\n\n"
        "¿Para qué día? (Ej: mañana, el 5 de mayo, viernes)\n\n"
        "9) Volver  0) Menú  X) Salir"
    )


async def _reschedule_date_input(business_id: int, user_key: str, context: dict, t: str, business_name: str) -> str:
    from app.utils.date_parse import resolve_date_from_spanish_text
    parsed = resolve_date_from_spanish_text(t)
    if not parsed:
        return "No pude interpretar esa fecha. Probá con: mañana, el 10 de mayo, viernes.\n\n9) Volver"
    # Don't persist the date until we confirm slots exist
    pending = {**(context.get("pending_data") or {})}
    return await _reschedule_fetch_slots(business_id, user_key, context, pending, business_name, target_date=parsed)


async def _reschedule_fetch_slots(
    business_id: int, user_key: str, context: dict, pending: dict, business_name: str,
    *, target_date=None,
) -> str:
    item = pending.get("selected_item") or _selected_item(context)
    target_date = target_date or pending.get("reschedule_date")
    service_id = (item or {}).get("service_id")

    if not target_date or not item:
        await _set_owner_idle(business_id, user_key)
        return "Perdí el contexto. Volvé a elegir la cita desde la agenda.\n\n" + owner_menu(business_name)

    if service_id is None:
        await _set_owner_idle(business_id, user_key)
        return "La cita no tiene servicio asignado; no puedo buscar disponibilidad. Contactá soporte.\n\n" + owner_menu(business_name)

    try:
        availability = await db_service.get_availability(
            business_id=business_id,
            service_id=service_id,
            date=str(target_date),
        )
        slots = availability.get("available_slots", [])
    except Exception as exc:
        logger.exception(
            "reschedule get_availability failed business=%s service=%s date=%s",
            business_id, service_id, target_date,
        )
        await _set_owner_idle(business_id, user_key)
        return "Error consultando disponibilidad. Intentá de nuevo.\n\n" + owner_menu(business_name)

    if not slots:
        # Clear any stale date so the owner can enter a new one cleanly
        pending_no_date = {k: v for k, v in pending.items() if k != "reschedule_date"}
        await _set_state(business_id, user_key, "owner_reschedule_ask_date", pending_no_date)
        return f"No hay disponibilidad el {target_date}. ¿Otro día?\n\n9) Volver"

    # Persist date + slots only after confirming availability
    new_pending = {**pending, "reschedule_date": target_date, "reschedule_slots": slots[:8]}
    await _set_state(business_id, user_key, "owner_reschedule_slots", new_pending)
    lines = [f"Horarios disponibles el {target_date}:\n"]
    for i, s in enumerate(slots[:8], 1):
        lines.append(f"{i}) {s.get('start_time')}")
    lines.append("\nElegí el número del horario.\n9) Volver  0) Menú")
    return "\n".join(lines)


async def _reschedule_slot_select(business_id: int, user_key: str, context: dict, t: str, business_name: str) -> str:
    pending = context.get("pending_data") or {}
    slots = pending.get("reschedule_slots") or []
    item = _selected_item(context)

    try:
        index = int(t) - 1
    except ValueError:
        # Try matching by time string
        index = next(
            (i for i, s in enumerate(slots) if t in str(s.get("start_time", "")).lower()),
            -1,
        )

    if index < 0 or index >= len(slots):
        lines = [f"Elegí un número entre 1 y {len(slots)}."]
        for i, s in enumerate(slots, 1):
            lines.append(f"{i}) {s.get('start_time')}")
        return "\n".join(lines) + "\n\n9) Volver"

    chosen = slots[index]
    new_pending = {**pending, "reschedule_chosen_slot": chosen}
    await _set_state(business_id, user_key, "owner_reschedule_confirm", new_pending)
    return (
        f"¿Confirmás reagendar cita #{(item or {}).get('appointment_id')} "
        f"a las <b>{chosen.get('start_time')}</b>?\n\n"
        "Respondé <b>sí</b> para confirmar o <b>no</b> para volver."
    )


async def _confirm_reschedule(business_id: int, user_key: str, context: dict, t: str, business_name: str) -> str:
    if _is_negative(t):
        # Back to slot selection
        pending = context.get("pending_data") or {}
        await _set_state(business_id, user_key, "owner_reschedule_slots", pending)
        slots = pending.get("reschedule_slots") or []
        lines = ["Volvemos a los horarios:\n"]
        for i, s in enumerate(slots, 1):
            lines.append(f"{i}) {s.get('start_time')}")
        return "\n".join(lines) + "\n\n9) Volver"

    if not _is_affirmative(t):
        return "No entendí. Respondé <b>sí</b> o <b>no</b>."

    pending = context.get("pending_data") or {}
    item = _selected_item(context)
    slot = pending.get("reschedule_chosen_slot")

    if not item or not slot:
        await _set_owner_idle(business_id, user_key)
        return "Perdí el contexto. Volvé a elegir la cita.\n\n" + owner_menu(business_name)

    start_datetime = slot.get("start_datetime")
    if not start_datetime:
        await _set_owner_idle(business_id, user_key)
        return "El horario seleccionado no tiene información completa. Intentá de nuevo.\n\n" + owner_menu(business_name)

    result = await owner_reschedule_appointment(
        item["appointment_id"], business_id, start_datetime
    )
    await _set_owner_idle(business_id, user_key)
    if result.ok:
        return (
            f"✅ Cita #{item['appointment_id']} reagendada a las {slot.get('start_time')}.\n\n"
            + owner_menu(business_name)
        )
    if result.error == "not_reschedulable":
        return "Esta cita no se puede reagendar (estado no es P ni C).\n\n" + owner_menu(business_name)
    return "No se pudo reagendar. Intentá de nuevo.\n\n" + owner_menu(business_name)


# ── Block timeslot flow ────────────────────────────────────────────────────────

async def _start_block(business_id: int, user_key: str) -> str:
    await _set_state(business_id, user_key, "owner_block_ask_date", {})
    return (
        "Vamos a bloquear un horario.\n\n"
        "¿Qué fecha querés bloquear? (Ej: hoy, mañana, el 5 de mayo)\n\n"
        "9) Volver  0) Menú  X) Salir"
    )


async def _block_date_input(business_id: int, user_key: str, t: str, tz: ZoneInfo = OWNER_TIMEZONE) -> str:
    from app.utils.date_parse import resolve_date_from_spanish_text
    from datetime import date as _date
    parsed = resolve_date_from_spanish_text(t)
    if not parsed:
        return "No pude interpretar esa fecha. Probá con: hoy, mañana, el 10 de mayo.\n\n9) Volver"
    if _date.fromisoformat(str(parsed)) < local_today(tz):
        return "No podés bloquear una fecha que ya pasó. Elegí una fecha presente o futura.\n\n9) Volver"
    await _set_state(business_id, user_key, "owner_block_ask_start", {"block_date": parsed})
    return f"Fecha: {parsed}\n\n¿Desde qué hora? (Ej: 2:00 PM, 14:00)\n\n9) Volver"


async def _block_start_input(business_id: int, user_key: str, context: dict, t: str) -> str:
    from app.utils.time_parser import parse_time_candidates
    pending = context.get("pending_data") or {}
    candidates = parse_time_candidates(t, allow_bare_hour=True)
    if not candidates:
        return "No pude interpretar esa hora. Probá con: 2:00 PM, 14:00.\n\n9) Volver"
    await _set_state(business_id, user_key, "owner_block_ask_end", {**pending, "block_start_time": candidates[0]})
    return f"Hora inicio: {candidates[0]}\n\n¿Hasta qué hora? (Ej: 4:00 PM, 16:00)\n\n9) Volver"


async def _block_end_input(business_id: int, user_key: str, context: dict, t: str, tz: ZoneInfo = OWNER_TIMEZONE) -> str:
    from app.utils.time_parser import parse_time_candidates
    pending = context.get("pending_data") or {}
    candidates = parse_time_candidates(t, allow_bare_hour=True)
    if not candidates:
        return "No pude interpretar esa hora. Probá con: 4:00 PM, 16:00.\n\n9) Volver"

    block_date = pending.get("block_date")
    start_str = pending.get("block_start_time")
    end_str = candidates[0]

    try:
        start_dt = _parse_local_dt(str(block_date), start_str, tz)
        end_dt = _parse_local_dt(str(block_date), end_str, tz)
    except Exception:
        return "No pude construir las fechas. Intentá de nuevo desde el inicio.\n\n9) Volver"

    if start_dt >= end_dt:
        return "La hora de fin debe ser después de la hora de inicio. ¿Hasta qué hora?\n\n9) Volver"

    new_pending = {**pending, "block_start_dt": start_dt.isoformat(), "block_end_dt": end_dt.isoformat()}
    await _set_state(business_id, user_key, "owner_block_confirm", new_pending)
    return (
        f"¿Confirmás bloquear el horario del <b>{block_date}</b> "
        f"de <b>{start_str}</b> a <b>{end_str}</b>?\n\n"
        "Respondé <b>sí</b> para confirmar o <b>no</b> para volver."
    )


def _parse_local_dt(date_str: str, time_str: str, tz: ZoneInfo = OWNER_TIMEZONE) -> datetime:
    """Combine date string (YYYY-MM-DD) and time string (HH:MM) into aware UTC datetime."""
    from datetime import date as date_type
    import re as _re
    m = _re.match(r"(\d{1,2}):(\d{2})", time_str)
    if not m:
        raise ValueError(f"Cannot parse time: {time_str}")
    h, mn = int(m.group(1)), int(m.group(2))
    d = date_type.fromisoformat(date_str)
    local_dt = datetime(d.year, d.month, d.day, h, mn, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)


async def _confirm_block(business_id: int, owner_id: int, user_key: str, context: dict, t: str, business_name: str) -> str:
    if _is_negative(t):
        await _set_owner_idle(business_id, user_key)
        return "Bloqueo cancelado.\n\n" + owner_menu(business_name)

    if not _is_affirmative(t):
        return "No entendí. Respondé <b>sí</b> para bloquear o <b>no</b> para cancelar."

    pending = context.get("pending_data") or {}
    start_str = pending.get("block_start_dt")
    end_str = pending.get("block_end_dt")

    if not start_str or not end_str:
        await _set_owner_idle(business_id, user_key)
        return "Perdí el contexto. Volvé a intentarlo.\n\n" + owner_menu(business_name)

    start_dt = datetime.fromisoformat(start_str)
    end_dt = datetime.fromisoformat(end_str)

    result = await owner_block_timeslot(business_id, owner_id, start_dt, end_dt)
    await _set_owner_idle(business_id, user_key)

    if result.ok:
        return "✅ Horario bloqueado correctamente.\n\n" + owner_menu(business_name)
    if result.error and result.error.startswith("conflict:"):
        names = result.error.split(":", 1)[1]
        return (
            f"⚠️ No se puede bloquear: hay citas activas en ese horario ({names}). "
            "Cancelalas primero desde la agenda.\n\n" + owner_menu(business_name)
        )
    if result.error == "invalid_window":
        return "El horario de fin debe ser posterior al de inicio.\n\n" + owner_menu(business_name)
    return "No se pudo bloquear el horario. Intentá de nuevo.\n\n" + owner_menu(business_name)


# ── Notifications toggle ───────────────────────────────────────────────────────

async def _toggle_notifications(business_id: int, owner_id: int, user_key: str, business_name: str) -> str:
    new_value = await db_service.toggle_business_notifications(business_id, owner_id)
    await _set_owner_idle(business_id, user_key)
    if new_value is None:
        return "No se pudo actualizar la configuración.\n\n" + owner_menu(business_name)
    state_text = "activadas ✅" if new_value else "desactivadas ❌"
    return f"Notificaciones diarias {state_text}.\n\n" + owner_menu(business_name)


# ── Main executor ──────────────────────────────────────────────────────────────

async def execute_owner_route(
    business_id: int,
    user_key: str,
    decision: OwnerRouteDecision,
    context: dict,
    *,
    owner_id: int,
    business_name: str,
) -> str:
    if decision.kind == "expired_session":
        await _clear_to_idle(business_id, user_key)
        return (
            "Cerré el panel rápido por inactividad. Te dejo el menú principal:\n\n"
            f"{owner_menu(business_name)}"
        )

    await conversation_manager.update_context(
        business_id, user_key,
        {"last_activity": datetime.now(timezone.utc).isoformat()},
    )

    biz_info = await db_service.get_business(business_id)
    tz_name: str = biz_info.get("timezone") or "America/Santo_Domingo"
    tz: ZoneInfo = _resolve_tz(tz_name)

    if decision.kind == "show_menu":
        await _set_owner_idle(business_id, user_key)
        return owner_menu(business_name)

    if decision.kind == "go_back":
        current_state = context.get("state") or "idle"
        if current_state == "owner_appointment_detail":
            return await _back_from_detail(business_id, user_key, context)
        if current_state in ("owner_cancel_confirm", "owner_complete_confirm"):
            # Return to appointment detail
            await _set_state(business_id, user_key, "owner_appointment_detail", context.get("pending_data") or {})
            item = _selected_item(context)
            return format_appointment_detail(item) if item else owner_menu(business_name)
        if current_state in ("owner_reschedule_ask_date", "owner_reschedule_slots", "owner_reschedule_confirm"):
            await _set_state(business_id, user_key, "owner_appointment_detail", context.get("pending_data") or {})
            item = _selected_item(context)
            return format_appointment_detail(item) if item else owner_menu(business_name)
        if current_state in ("owner_block_ask_date", "owner_block_ask_start", "owner_block_ask_end", "owner_block_confirm"):
            await _set_owner_idle(business_id, user_key)
            return owner_menu(business_name)
        await _set_owner_idle(business_id, user_key)
        return owner_menu(business_name)

    if decision.kind == "exit_session":
        await _clear_to_idle(business_id, user_key)
        return 'Listo, cerré el panel rápido. Para volver, escribí "menu".'

    if decision.kind == "menu_option":
        if decision.option == "1":
            return await _agenda_today(owner_id, business_id, user_key, tz_name)
        if decision.option == "2":
            return await _agenda_tomorrow(owner_id, business_id, user_key, tz_name)
        if decision.option == "3":
            return await _upcoming(owner_id, business_id, user_key, tz_name)
        if decision.option == "4":
            return await _metrics_today(owner_id, business_id, user_key, tz_name)
        if decision.option == "5":
            return await _toggle_notifications(business_id, owner_id, user_key, business_name)
        if decision.option == "6":
            return await _start_block(business_id, user_key)

    if decision.kind == "agenda_detail":
        return await _agenda_detail(business_id, user_key, context, decision.option)

    # Actions from appointment detail
    if decision.kind == "action_cancel":
        return await _start_cancel(business_id, user_key, context)

    if decision.kind == "action_complete":
        return await _start_complete(business_id, user_key, context)

    if decision.kind == "action_reschedule":
        return await _start_reschedule(business_id, user_key, context)

    # In-flow inputs
    if decision.kind == "flow_input":
        t = decision.option or ""
        current_state = context.get("state") or "idle"

        if current_state == "owner_cancel_confirm":
            return await _confirm_cancel(business_id, user_key, context, t, business_name)

        if current_state == "owner_complete_confirm":
            return await _confirm_complete(business_id, user_key, context, t, business_name)

        if current_state == "owner_reschedule_ask_date":
            pending = context.get("pending_data") or {}
            if pending.get("reschedule_date"):
                # Date already set — treat as slot selection re-entry (shouldn't normally hit)
                return await _reschedule_fetch_slots(business_id, user_key, context, pending, business_name)
            return await _reschedule_date_input(business_id, user_key, context, t, business_name)

        if current_state == "owner_reschedule_slots":
            return await _reschedule_slot_select(business_id, user_key, context, t, business_name)

        if current_state == "owner_reschedule_confirm":
            return await _confirm_reschedule(business_id, user_key, context, t, business_name)

        if current_state == "owner_block_ask_date":
            return await _block_date_input(business_id, user_key, t, tz)

        if current_state == "owner_block_ask_start":
            return await _block_start_input(business_id, user_key, context, t)

        if current_state == "owner_block_ask_end":
            return await _block_end_input(business_id, user_key, context, t, tz)

        if current_state == "owner_block_confirm":
            return await _confirm_block(business_id, owner_id, user_key, context, t, business_name)

    await _set_owner_idle(business_id, user_key)
    return owner_menu(business_name)
