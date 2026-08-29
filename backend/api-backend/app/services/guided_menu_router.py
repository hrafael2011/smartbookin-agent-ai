"""Guided menu routing shared by WhatsApp and Telegram customer channels."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from app.config import config
from app.core.response_builder import BotReply
from app.handlers.booking_handler import (
    handle_book_appointment,
    handle_booking_confirmation,
    render_slots_reply,
)
from app.handlers.booking_calendar_handler import (
    handle_booking_day,
    handle_booking_month,
    handle_booking_week,
)
from app.handlers.business_info_handler import handle_business_info
from app.handlers.cancel_handler import handle_cancel_appointment
from app.handlers.check_handler import handle_check_appointment
from app.handlers.modify_handler import handle_modify_appointment
from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.services.no_services_nlu import NO_SERVICES_GENERIC
from app.utils import telegram_ui
from app.utils.conversation_routing import (
    is_random_or_greeting,
    is_short_confirmation_message,
    parse_menu_choice,
)
from app.utils.date_parse import format_date_human_es

ACTIVE_FLOW_TIMEOUT_SECONDS = 30 * 60

_MAIN_MENU_WORDS = {
    "0",
    "menu",
    "menú",
    "inicio",
    "menu principal",
    "menú principal",
}
_BACK_WORDS = {"9", "volver", "atras", "atrás"}
_EXIT_WORDS = {"x", "salir", "terminar", "cerrar", "cerrar consulta"}


@dataclass(frozen=True)
class RouteDecision:
    kind: str
    option: Optional[str] = None
    reason: str = ""
    uses_ai: bool = False
    counts_total: bool = True
    payload: Optional[Dict] = None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _is_active_context(context: dict) -> bool:
    return (context.get("state") or "idle") != "idle"


def _is_expired_active_flow(context: dict) -> bool:
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
    return (datetime.now(timezone.utc) - last).total_seconds() > ACTIVE_FLOW_TIMEOUT_SECONDS


def _is_abusive(text: str) -> bool:
    t = _norm(text)
    if not t:
        return False
    # Conservative list: only clear insults/profanity, avoiding broad words that can be names.
    abusive_terms = (
        "idiota",
        "estupido",
        "estúpido",
        "imbecil",
        "imbécil",
        "maldito",
        "mierda",
        "vete al diablo",
        "vete a la",
        "pendejo",
        "cabrón",
        "cabron",
        "mamaguevo",
        "malparido",
        "singao",
        "coño tu",
        "tu madre",
        "cono tu",
        "inutil",
        "inútil",
        "basura de bot",
        "fuck",
        "shit",
        "asshole",
        "bastard",
    )
    return any(term in t for term in abusive_terms)


def _is_out_of_domain(text: str) -> bool:
    t = _norm(text)
    if not t:
        return False
    out_of_domain_terms = (
        "carro",
        "vehiculo",
        "vehículo",
        "politica",
        "política",
        "bitcoin",
        "criptomoneda",
        "tarea escolar",
        "programame",
        "hazme una app",
        "receta de cocina",
        "chiste",
        "cuéntame un chiste",
        "cuentame un chiste",
        "qué hora es",
        "que hora es",
        "el tiempo",
        "clima",
        "pronóstico",
        "pronostico",
        "lotería",
        "loteria",
        "futbol",
        "fútbol",
        "partido",
        "noticias",
        "filosofia",
        "filosofía",
        "poema",
        "tradúceme",
        "traduceme",
        "matematica",
        "matemática",
        "historia de",
        "quién inventó",
        "quien invento",
    )
    domain_terms = (
        "cita",
        "turno",
        "agendar",
        "reservar",
        "horario",
        "servicio",
        "precio",
        "ubicacion",
        "ubicación",
        "direccion",
        "dirección",
        "cancelar",
        "cambiar",
        "reagendar",
    )
    return any(term in t for term in out_of_domain_terms) and not any(
        term in t for term in domain_terms
    )


def _looks_ambiguous(text: str) -> bool:
    t = _norm(text)
    if not t:
        return True
    if len(t) <= 2:
        return True
    ambiguous = {
        "eso",
        "eso mismo",
        "lo mismo",
        "dame eso",
        "quiero eso",
        "ok",
        "oki",
        "gracias",
    }
    return t in ambiguous


def _looks_business_info(text: str) -> bool:
    t = _norm(text)
    phrases = (
        "horario",
        "horarios",
        "ubicacion",
        "ubicación",
        "direccion",
        "dirección",
        "donde estan",
        "dónde están",
        "donde queda",
        "qué horario",
        "que horario",
    )
    return any(p in t for p in phrases)


def _looks_services(text: str) -> bool:
    t = _norm(text)
    phrases = (
        "que servicios",
        "qué servicios",
        "servicios ofreces",
        "servicios ofrece",
        "ver servicios",
        "mostrar servicios",
        "lista de servicios",
        "catalogo",
        "catálogo",
    )
    return any(p in t for p in phrases)


def route_guided_message(message_text: str, context: dict) -> RouteDecision:
    """Classify a user message before channel quota and NLU decisions."""
    t = _norm(message_text)

    if _is_expired_active_flow(context):
        return RouteDecision("expired_flow", reason="active_flow_timeout")

    # Callback inline: id único y semántico ligado al contexto (nunca se reutiliza
    # el mismo id para significados distintos entre pantallas).
    callback = telegram_ui.parse_inline_callback(message_text)
    if callback:
        return RouteDecision(
            "inline_callback",
            payload=callback,
            reason=f"callback_{callback['ns']}",
        )

    if t in _MAIN_MENU_WORDS:
        return RouteDecision("go_main_menu" if _is_active_context(context) else "show_menu", reason="main_menu")
    if _is_active_context(context) and t in _BACK_WORDS:
        return RouteDecision("go_back", reason="back")
    if _is_active_context(context) and t in _EXIT_WORDS:
        return RouteDecision("exit_flow", reason="exit")

    if _is_active_context(context):
        deterministic_active = t.isdigit() or is_short_confirmation_message(message_text)
        return RouteDecision(
            "active_flow",
            reason="active_flow",
            uses_ai=config.ai_enabled and not deterministic_active,
        )

    choice = parse_menu_choice(message_text)
    if choice == "menu":
        return RouteDecision("show_menu", reason="menu_command")
    # Bug #2: en idle, un dígito solo se interpreta como opción del menú si la
    # pantalla visible es el menú principal. Tras una pregunta abierta (last_screen
    # distinto), cae al pipeline NLU (fallback ambiguo → menú con botones).
    if choice in {"1", "2", "3", "4", "5"} and context.get("last_screen") == "main_menu":
        return RouteDecision("menu_option", option=choice, reason=f"option_{choice}")
    if is_random_or_greeting(message_text):
        return RouteDecision("show_menu", reason="greeting")

    if _is_abusive(message_text):
        return RouteDecision("abusive", reason="abusive")
    if _is_out_of_domain(message_text):
        return RouteDecision("out_of_domain", reason="out_of_domain")
    if _looks_ambiguous(message_text):
        return RouteDecision("ambiguous_fallback", reason="ambiguous")
    if _looks_services(message_text):
        return RouteDecision("business_services", reason="services")
    if _looks_business_info(message_text):
        return RouteDecision("business_info", reason="business_info")

    booking_words = ("agendar", "reservar", "cita", "turno")
    if any(word in t for word in booking_words):
        return RouteDecision("direct_shortcut", reason="booking_shortcut", uses_ai=config.ai_enabled)

    return RouteDecision("pass_to_nlu", reason="needs_interpretation", uses_ai=config.ai_enabled)


def _with_menu(prefix: str, customer_name: str = "") -> BotReply:
    return telegram_ui.main_menu_reply(prefix, customer_name)


async def _clear_to_idle(business_id: int, user_key: str) -> None:
    await conversation_manager.update_context(
        business_id,
        user_key,
        {
            "current_intent": None,
            "pending_data": {},
            "state": "idle",
            "last_screen": None,
        },
    )


async def _start_booking(business_id: int, user_key: str) -> BotReply:
    services = await db_service.get_business_services(business_id)
    if not services:
        return BotReply(
            NO_SERVICES_GENERIC,
            keyboard=telegram_ui.with_footer([]),
        )
    await conversation_manager.update_context(
        business_id,
        user_key,
        {
            "current_intent": "book_appointment",
            "state": "awaiting_service",
            "pending_data": {},
        },
    )
    return BotReply(
        "Perfecto. ¿Qué servicio querés reservar?",
        keyboard=telegram_ui.with_footer(telegram_ui.service_buttons(services)),
    )


async def _mark_main_menu(business_id: int, user_key: str) -> None:
    await conversation_manager.mark_main_menu(business_id, user_key)


async def _go_back(business_id: int, user_key: str, context: dict) -> BotReply:
    stack = list(context.get("state_stack") or [])
    if stack:
        prev_state = stack.pop()
        await conversation_manager.update_context(
            business_id,
            user_key,
            {
                "state": prev_state,
                "state_stack": stack,
            },
        )
        return BotReply("Volvemos al paso anterior.", keyboard=telegram_ui.with_footer([]))
    await _clear_to_idle(business_id, user_key)
    await _mark_main_menu(business_id, user_key)
    return telegram_ui.guided_menu_reply(context.get("customer_name") or "")


async def _go_main_menu(business_id: int, user_key: str, customer_name: str) -> BotReply:
    await _clear_to_idle(business_id, user_key)
    await _mark_main_menu(business_id, user_key)
    return telegram_ui.main_menu_reply(customer_name=customer_name)


async def _exit_flow(business_id: int, user_key: str) -> BotReply:
    await _clear_to_idle(business_id, user_key)
    return BotReply('Listo, cerré esta consulta. Cuando necesités algo, escribí "menu".')


async def _start_modify(business_id: int, user_key: str, context: dict) -> BotReply:
    return await handle_modify_appointment(
        {
            "intent": "modify_appointment",
            "entities": {},
            "missing": [],
            "_raw_user_text": "",
        },
        context,
    )


async def _start_cancel(business_id: int, user_key: str, context: dict) -> BotReply:
    return await handle_cancel_appointment(
        {
            "intent": "cancel_appointment",
            "entities": {},
            "missing": [],
            "_raw_user_text": "",
        },
        context,
    )


def _callback_valid_for_state(ns: str, context: dict) -> bool:
    """Un callback solo se ejecuta si corresponde al paso actual del flujo."""
    state = context.get("state") or "idle"
    intent = context.get("current_intent")
    if ns in ("nav", "menu"):
        return True
    if ns == "service":
        return intent == "book_appointment"
    if ns == "day":
        if intent == "book_appointment":
            return state in ("awaiting_date", "booking_current_week", "booking_day")
        if intent == "modify_appointment":
            return state in ("awaiting_new_date", "awaiting_new_datetime")
        return False
    if ns == "time":
        if state == "awaiting_slot_selection":
            return intent == "book_appointment"
        return state in ("awaiting_slot_selection_modify", "awaiting_new_time")
    if ns == "slots_page":
        return state in ("awaiting_slot_selection", "awaiting_slot_selection_modify", "awaiting_new_time")
    if ns == "confirm":
        return state == "awaiting_booking_confirmation"
    if ns == "cancel_appt":
        return intent == "cancel_appointment"
    if ns == "cancel_confirm":
        return state == "awaiting_cancel_confirmation"
    if ns == "modify_appt":
        return intent == "modify_appointment"
    if ns == "month":
        return state == "booking_month"
    if ns == "month_browse":
        return state == "booking_current_week"
    if ns == "week":
        return state == "booking_week"
    if ns == "resume":
        return state == "awaiting_session_resume"
    return False


def _stale_reply() -> BotReply:
    return telegram_ui.main_menu_reply("Esa opción ya no está vigente. Elegí del menú:")


async def _handle_modify_day(business_id: int, user_key: str, date_str: str, context: dict) -> BotReply:
    """day_* en flujo de modificación: fija new_date y muestra la grilla de horarios."""
    pending = {**context.get("pending_data", {})}
    pending["new_date"] = date_str
    service_id = int(pending.get("service_id") or 0)
    availability = (
        await db_service.get_availability(
            business_id=business_id,
            service_id=service_id,
            date=date_str,
            preferred_time=None,
        )
        if service_id
        else {"available_slots": []}
    )
    slots = availability.get("available_slots", [])
    pending["available_slots"] = slots
    pending["slot_page"] = 0
    await conversation_manager.update_context(
        business_id,
        user_key,
        {
            "current_intent": "modify_appointment",
            "state": "awaiting_new_time",
            "pending_data": pending,
        },
    )
    if not slots:
        return BotReply(
            f"No hay disponibilidad para el <b>{format_date_human_es(date_str)}</b>. "
            "Elegí otro día:",
            keyboard=telegram_ui.with_footer(
                telegram_ui.day_buttons(await _modify_available_days(business_id, service_id, context))
            ),
        )
    return render_slots_reply(pending, page=0)


async def _modify_available_days(business_id: int, service_id: int, context: dict) -> list:
    if not service_id:
        return []
    from datetime import date as date_type
    from datetime import timedelta

    today = datetime.now(timezone.utc).date()
    days = await db_service.get_available_days_in_range(
        business_id=business_id,
        service_id=service_id,
        start_date=today,
        end_date=today + timedelta(days=13),
    )
    return days


async def _handle_inline_callback(
    business_id: int,
    user_key: str,
    payload: Dict,
    context: dict,
) -> BotReply:
    ns = payload["ns"]
    value = payload["value"]
    customer_name = context.get("customer_name") or ""

    if not _callback_valid_for_state(ns, context):
        await _clear_to_idle(business_id, user_key)
        await _mark_main_menu(business_id, user_key)
        return _stale_reply()

    if ns == "nav":
        if value == "back":
            return await _go_back(business_id, user_key, context)
        if value == "menu":
            return await _go_main_menu(business_id, user_key, customer_name)
        if value == "exit":
            return await _exit_flow(business_id, user_key)

    if ns == "menu":
        if value == "agendar":
            return await _start_booking(business_id, user_key)
        if value == "ver_citas":
            return await handle_check_appointment({}, context)
        if value == "cambiar":
            return await _start_modify(business_id, user_key, context)
        if value == "cancelar":
            return await _start_cancel(business_id, user_key, context)
        if value == "horarios":
            return await handle_business_info(business_id)

    if ns == "service":
        services = await db_service.get_business_services(business_id)
        service = next((s for s in services if str(s.get("id")) == str(value)), None)
        if not service:
            return BotReply(
                "No encontré ese servicio. Elegí de la lista:",
                keyboard=telegram_ui.with_footer(telegram_ui.service_buttons(services)),
            )
        pending = {
            **context.get("pending_data", {}),
            "service": service["name"],
            "service_id": service["id"],
        }
        await conversation_manager.update_context(business_id, user_key, {"pending_data": pending})
        return await handle_book_appointment(
            {"_raw_user_text": "", "entities": {}, "missing": []},
            {**context, "pending_data": pending},
        )

    if ns == "day":
        if context.get("current_intent") == "modify_appointment":
            return await _handle_modify_day(business_id, user_key, str(value), context)
        pending = {**context.get("pending_data", {}), "date": str(value)}
        await conversation_manager.update_context(business_id, user_key, {"pending_data": pending})
        return await handle_book_appointment(
            {"_raw_user_text": "", "entities": {"date": str(value)}, "missing": []},
            {**context, "pending_data": pending},
        )

    if ns == "time":
        date_str, hhmm = value
        pending = context.get("pending_data", {})
        if str(pending.get("date")) != str(date_str) and not context.get("current_intent") == "modify_appointment":
            return _stale_reply()
        slot = telegram_ui.slot_by_hhmm(pending.get("available_slots") or [], str(hhmm))
        if not slot:
            return _stale_reply()
        if context.get("current_intent") == "modify_appointment":
            return await handle_modify_appointment(
                {"_raw_user_text": str(slot.get("start_time", "")), "entities": {"time": slot.get("start_time", "")}},
                context,
            )
        updated = {**pending, "selected_slot": slot}
        await conversation_manager.update_context(business_id, user_key, {"pending_data": updated})
        return await handle_book_appointment(
            {"_raw_user_text": "", "entities": {}, "missing": []},
            {**context, "pending_data": updated},
        )

    if ns == "slots_page":
        page = max(0, int(value))
        pending = {**context.get("pending_data", {}), "slot_page": page}
        await conversation_manager.update_context(business_id, user_key, {"pending_data": pending})
        return render_slots_reply(pending, page=page)

    if ns == "confirm":
        raw = "sí" if value == "yes" else "no"
        return await handle_booking_confirmation(
            {"_raw_user_text": raw, "entities": {}, "missing": []},
            context,
        )

    if ns == "cancel_appt":
        appt = await db_service.get_customer_appointment(
            int(value), int(context.get("customer_id") or 0)
        )
        if not appt:
            return _stale_reply()
        await conversation_manager.update_context(
            business_id,
            user_key,
            {
                "current_intent": "cancel_appointment",
                "state": "awaiting_cancel_confirmation",
                "pending_data": {"appointment_id": appt["id"]},
            },
        )
        start = datetime.fromisoformat(str(appt["start_at"]).replace("Z", "+00:00"))
        return BotReply(
            f"Vas a cancelar:\n"
            f"📅 {start.strftime('%A %d de %B')}\n"
            f"⏰ {start.strftime('%I:%M %p')}\n"
            f"✂️ {appt['service_name']}\n\n"
            "¿Confirmás la cancelación?",
            keyboard=telegram_ui.with_footer(telegram_ui.cancel_confirm_buttons()),
        )

    if ns == "cancel_confirm":
        appointment_id = int((context.get("pending_data") or {}).get("appointment_id") or 0)
        if value == "no":
            await _clear_to_idle(business_id, user_key)
            await _mark_main_menu(business_id, user_key)
            return telegram_ui.main_menu_reply("Entendido, tu cita se mantiene.", customer_name)
        await db_service.cancel_appointment(appointment_id=appointment_id, notes="Cancelado por el cliente vía Telegram")
        await _clear_to_idle(business_id, user_key)
        await _mark_main_menu(business_id, user_key)
        return telegram_ui.main_menu_reply("✅ Tu cita ha sido cancelada exitosamente.", customer_name)

    if ns == "modify_appt":
        appt = await db_service.get_customer_appointment(
            int(value), int(context.get("customer_id") or 0)
        )
        if not appt:
            return _stale_reply()
        service_id = int(appt.get("service_id") or 0)
        days = await _modify_available_days(business_id, service_id, context)
        pending = {
            "selected_appointment_id": appt["id"],
            "service_id": service_id,
            "service_name": appt.get("service_name", ""),
        }
        await conversation_manager.update_context(
            business_id,
            user_key,
            {
                "current_intent": "modify_appointment",
                "state": "awaiting_new_date",
                "pending_data": pending,
            },
        )
        if not days:
            return BotReply(
                "No encontré disponibilidad en los próximos días.",
                keyboard=telegram_ui.with_footer([]),
            )
        return BotReply(
            "¿Para cuándo querés reagendar?",
            keyboard=telegram_ui.with_footer(telegram_ui.day_buttons(days)),
        )

    if ns == "month":
        return await handle_booking_week(business_id, user_key, int(value), context)

    if ns == "month_browse":
        return await handle_booking_month(business_id, user_key, context)

    if ns == "week":
        return await handle_booking_day(business_id, user_key, int(value), context)

    if ns == "resume":
        if value == "yes":
            await conversation_manager.update_context(
                business_id,
                user_key,
                {
                    "state": context.get("resume_state") or "idle",
                    "current_intent": context.get("resume_intent"),
                    "pending_data": context.get("resume_data") or {},
                    "resume_data": None,
                    "resume_intent": None,
                    "resume_state": None,
                },
            )
            return BotReply("Listo, continuamos. Te retomo desde donde estabas.", keyboard=telegram_ui.with_footer([]))
        await _clear_to_idle(business_id, user_key)
        await _mark_main_menu(business_id, user_key)
        return telegram_ui.main_menu_reply("Entendido. Cerramos esa consulta.", customer_name)

    return _stale_reply()


async def execute_guided_route(
    business_id: int,
    user_key: str,
    decision: RouteDecision,
    context: dict,
) -> Optional[BotReply]:
    """Execute deterministic guided route. None means caller should continue."""
    customer_name = context.get("customer_name") or ""

    if decision.kind == "inline_callback":
        return await _handle_inline_callback(business_id, user_key, decision.payload or {}, context)

    if decision.kind == "show_menu":
        await _mark_main_menu(business_id, user_key)
        return telegram_ui.guided_menu_reply(customer_name)

    if decision.kind == "go_main_menu":
        return await _go_main_menu(business_id, user_key, customer_name)

    if decision.kind == "go_back":
        return await _go_back(business_id, user_key, context)

    if decision.kind == "exit_flow":
        return await _exit_flow(business_id, user_key)

    if decision.kind == "expired_flow":
        pending_data = context.get("pending_data") or {}
        if pending_data:
            await conversation_manager.update_context(
                business_id,
                user_key,
                {
                    "state": "awaiting_session_resume",
                    "resume_data": pending_data,
                    "resume_intent": context.get("current_intent"),
                    "resume_state": context.get("state"),
                },
            )
            return BotReply(
                "Tenías una consulta a medias. ¿Continuamos donde estabas?",
                keyboard=telegram_ui.with_footer(telegram_ui.resume_buttons()),
            )
        await _clear_to_idle(business_id, user_key)
        await _mark_main_menu(business_id, user_key)
        return _with_menu(
            "Cerré la consulta anterior por inactividad. Te dejo el menú principal:",
            customer_name,
        )

    if decision.kind == "ambiguous_fallback":
        await _mark_main_menu(business_id, user_key)
        return _with_menu("No estoy seguro de qué querés hacer. Elegí una opción:", customer_name)

    if decision.kind == "out_of_domain":
        await _mark_main_menu(business_id, user_key)
        return _with_menu(
            "Este asistente gestiona citas del negocio. Para otras consultas, contactá directamente al local.",
            customer_name,
        )

    if decision.kind == "abusive":
        await _mark_main_menu(business_id, user_key)
        return _with_menu(
            "Por favor mantengamos un trato cordial. Estoy aquí para ayudarte con tus citas.",
            customer_name,
        )

    if decision.kind == "business_info":
        return await handle_business_info(business_id)

    if decision.kind == "business_services":
        from app.handlers.business_info_handler import handle_business_services

        return await handle_business_services(business_id)

    if decision.kind == "menu_option":
        if decision.option == "1":
            return await _start_booking(business_id, user_key)
        if decision.option == "2":
            return await handle_check_appointment({}, context)
        if decision.option == "3":
            return await _start_modify(business_id, user_key, context)
        if decision.option == "4":
            return await _start_cancel(business_id, user_key, context)
        if decision.option == "5":
            return await handle_business_info(business_id)

    return None
