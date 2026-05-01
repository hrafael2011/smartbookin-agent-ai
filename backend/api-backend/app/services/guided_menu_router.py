"""Guided menu routing shared by WhatsApp and Telegram customer channels."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.handlers.business_info_handler import handle_business_info
from app.handlers.check_handler import handle_check_appointment
from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.services.no_services_nlu import NO_SERVICES_GENERIC
from app.utils.conversation_routing import (
    guided_menu,
    is_random_or_greeting,
    is_short_confirmation_message,
    parse_menu_choice,
)

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
        "fuck",
        "shit",
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
            uses_ai=not deterministic_active,
        )

    choice = parse_menu_choice(message_text)
    if choice == "menu":
        return RouteDecision("show_menu", reason="menu_command")
    if choice in {"1", "2", "3", "4", "5"}:
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
        return RouteDecision("direct_shortcut", reason="booking_shortcut", uses_ai=True)

    return RouteDecision("pass_to_nlu", reason="needs_interpretation", uses_ai=True)


def _with_menu(prefix: str, customer_name: str = "") -> str:
    return f"{prefix}\n\n{guided_menu(customer_name)}"


async def _clear_to_idle(business_id: int, user_key: str) -> None:
    await conversation_manager.update_context(
        business_id,
        user_key,
        {
            "current_intent": None,
            "pending_data": {},
            "state": "idle",
        },
    )


async def _start_booking(business_id: int, user_key: str) -> str:
    services = await db_service.get_business_services(business_id)
    if not services:
        return NO_SERVICES_GENERIC
    services_text = "\n".join(
        f"  {i}. {s['name']} (${s['price']}, {s['duration_minutes']} min)"
        for i, s in enumerate(services, 1)
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
    return (
        "Perfecto. ¿Qué servicio querés reservar?\n\n"
        f"{services_text}\n\n"
        "9) Volver\n0) Menú principal\nX) Salir"
    )


async def execute_guided_route(
    business_id: int,
    user_key: str,
    decision: RouteDecision,
    context: dict,
) -> Optional[str]:
    """Execute deterministic guided route. None means caller should continue."""
    customer_name = context.get("customer_name") or ""

    if decision.kind == "show_menu":
        return guided_menu(customer_name)

    if decision.kind == "go_main_menu":
        await _clear_to_idle(business_id, user_key)
        return guided_menu(customer_name)

    if decision.kind == "go_back":
        # Phase 1 fallback: no reliable navigation stack yet.
        await _clear_to_idle(business_id, user_key)
        return guided_menu(customer_name)

    if decision.kind == "exit_flow":
        await _clear_to_idle(business_id, user_key)
        return 'Listo, cerré esta consulta. Cuando necesités algo, escribí "menu".'

    if decision.kind == "expired_flow":
        await _clear_to_idle(business_id, user_key)
        return _with_menu("Cerré la consulta anterior por inactividad. Te dejo el menú principal:", customer_name)

    if decision.kind == "ambiguous_fallback":
        return _with_menu("No estoy seguro de qué querés hacer. Elegí una opción:", customer_name)

    if decision.kind == "out_of_domain":
        return _with_menu(
            "Por ahora puedo ayudarte con citas, servicios, horarios y ubicación del negocio. Elegí una opción:",
            customer_name,
        )

    if decision.kind == "abusive":
        return _with_menu(
            "Estoy aquí para ayudarte con citas del negocio. Si querés continuar, elegí una opción:",
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
            await conversation_manager.update_context(
                business_id,
                user_key,
                {
                    "current_intent": "modify_appointment",
                    "state": "awaiting_appointment_selection_modify",
                },
            )
            return "Perfecto. Decime qué cita querés cambiar y te ayudo.\n\n9) Volver\n0) Menú principal\nX) Salir"
        if decision.option == "4":
            await conversation_manager.update_context(
                business_id,
                user_key,
                {
                    "current_intent": "cancel_appointment",
                    "state": "awaiting_appointment_selection",
                },
            )
            return "Entendido. Decime cuál cita querés cancelar.\n\n9) Volver\n0) Menú principal\nX) Salir"
        if decision.option == "5":
            return await handle_business_info(business_id)

    return None
