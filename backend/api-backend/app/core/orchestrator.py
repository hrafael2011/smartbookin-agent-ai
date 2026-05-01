"""
Orquestador del turno conversacional: NLU, interpretación de flujo y dispatch a handlers.
Unifica la lógica que antes estaba duplicada entre WhatsApp (main.py) y Telegram (telegram_inbound).
"""
from __future__ import annotations

from typing import Any, Dict

from app.config import config
from app.core.conversation_states import Intent, State
from app.core.response_builder import EMPTY_REPLY_PLACEHOLDER
from app.core.state_machine import ensure_coherent_context
from app.handlers.booking_handler import (
    handle_book_appointment,
    handle_booking_confirmation,
    handle_slot_selection,
)
from app.handlers.business_info_handler import handle_business_info, handle_business_services
from app.handlers.cancel_handler import handle_cancel_appointment
from app.handlers.check_handler import handle_check_appointment
from app.handlers.modify_handler import handle_modify_appointment
from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.services.customer_context_builder import build_customer_context_for_nlu
from app.services.nlu_engine import nlu_engine
from app.utils.date_parse import resolve_date_from_spanish_text, weekday_mismatch
from app.utils.flow_interpreter import (
    try_booking_flow_synthetic_nlu,
    user_message_looks_like_booking_correction,
)
from app.utils.time_parser import daypart_preference_hhmm_range, parse_time_candidates
from app.utils.conversation_routing import guided_menu, is_short_confirmation_message, parse_menu_choice


def _apply_python_date_authority(nlu_result: Dict[str, Any], message_text: str) -> None:
    """
    La fecha canónica en entities['date'] (YYYY-MM-DD) la define Python a partir del texto,
    corrigiendo ISO incoherente con el mensaje y usando date_raw si el modelo lo envía.
    """
    entities = nlu_result.setdefault("entities", {})
    blob = (message_text or "").strip()
    date_raw = entities.pop("date_raw", None)
    if date_raw:
        blob = f"{date_raw} {blob}".strip()
    resolved = resolve_date_from_spanish_text(blob) or resolve_date_from_spanish_text(
        message_text or ""
    )
    existing = entities.get("date")
    if resolved:
        if not existing or weekday_mismatch(str(existing), message_text or ""):
            entities["date"] = resolved
    elif existing and weekday_mismatch(str(existing), message_text or ""):
        fixed = resolve_date_from_spanish_text(message_text or "")
        if fixed:
            entities["date"] = fixed


def _match_idle_capability_route(message_text: str) -> str | None:
    t = (message_text or "").strip().lower()
    if not t:
        return None

    if parse_menu_choice(t) == "menu":
        return "menu"

    # Intención corta de reagendar (evita caer en respuesta conversacional ambigua)
    if t in ("cambiar", "cámbiar", "modificar", "reagendar"):
        return "modify"

    if any(
        phrase in t
        for phrase in (
            "menu de inicio",
            "menú de inicio",
            "mostrar menu",
            "mostrar menú",
            "ver menu",
            "ver menú",
            "menu principal",
            "menú principal",
            "que puedo hacer",
            "qué puedo hacer",
            "ayudame con el menu",
            "ayúdame con el menú",
        )
    ):
        return "menu"

    if any(
        phrase in t
        for phrase in (
            "que servicios",
            "qué servicios",
            "servicios ofreces",
            "servicios ofrece",
            "ensename los servicios",
            "enséñame los servicios",
            "mostrar servicios",
            "ver servicios",
            "lista de servicios",
            "catalogo",
            "catálogo",
        )
    ):
        return "services"

    if any(
        phrase in t
        for phrase in (
            "como cancelar",
            "cómo cancelar",
            "cancelar una cita",
            "cancelar mi cita",
            "quiero cancelar",
            "puedo cancelar",
            "se puede cancelar",
        )
    ):
        return "cancel"

    if any(
        phrase in t
        for phrase in (
            "como cambiar",
            "cómo cambiar",
            "modificar una cita",
            "cambiar una cita",
            "reagendar una cita",
            "quiero cambiar",
            "quiero modificar",
        )
    ):
        return "modify"

    if any(
        phrase in t
        for phrase in (
            "mis citas",
            "citas activas",
            "citas proximas",
            "citas próximas",
            "ver mis citas",
            "mostrar mis citas",
            "tengo citas",
        )
    ):
        return "check"

    return None


async def run_conversation_turn(
    business_id: int,
    user_key: str,
    message_text: str,
) -> str:
    """
    Persiste el mensaje del usuario, ejecuta NLU (o atajos), despacha al handler adecuado
    y devuelve el texto de respuesta (sin enviarlo por canal).
    """
    await conversation_manager.save_message(business_id, user_key, "user", message_text)
    context = await conversation_manager.get_context(business_id, user_key)
    context = await ensure_coherent_context(business_id, user_key, context)
    customer_id = context.get("customer_id")
    current_state = context.get("state", State.IDLE.value)
    current_intent = context.get("current_intent")

    # En idle, algunas capacidades del sistema deben resolverse sin dejar espacio a alucinaciones
    # del LLM sobre lo que el bot puede o no puede hacer.
    if current_state == State.IDLE.value:
        capability_route = _match_idle_capability_route(message_text)
        if capability_route == "menu":
            response_text = guided_menu(context.get("customer_name") or "")
        elif capability_route == "services":
            response_text = await handle_business_services(business_id)
        elif capability_route == "cancel":
            response_text = await handle_cancel_appointment(
                {"intent": Intent.CANCEL_APPOINTMENT.value, "entities": {}, "_raw_user_text": message_text},
                context,
            )
        elif capability_route == "modify":
            response_text = await handle_modify_appointment(
                {"intent": Intent.MODIFY_APPOINTMENT.value, "entities": {}, "_raw_user_text": message_text},
                context,
            )
        elif capability_route == "check":
            response_text = await handle_check_appointment(
                {"intent": Intent.CHECK_APPOINTMENT.value, "entities": {}, "_raw_user_text": message_text},
                context,
            )
        else:
            response_text = None

        if response_text:
            await conversation_manager.save_message(
                business_id, user_key, "assistant", response_text
            )
            return response_text

    st = context.get("state")
    if st in (
        State.AWAITING_BOOKING_CONFIRMATION.value,
        State.AWAITING_CANCEL_CONFIRMATION.value,
    ) and is_short_confirmation_message(message_text):
        nlu_result: Dict[str, Any] = {
            "intent": Intent.BOOK_APPOINTMENT.value
            if st == State.AWAITING_BOOKING_CONFIRMATION.value
            else Intent.CANCEL_APPOINTMENT.value,
            "confidence": 1.0,
            "entities": {},
            "missing": [],
            "raw_understanding": "confirmation_shortcut",
            "response_text": "",
        }
    else:
        customer_context_str = await build_customer_context_for_nlu(
            context.get("customer_id"),
            context.get("customer_name") or "Cliente",
            context.get("recent_messages"),
        )
        flow_nlu = try_booking_flow_synthetic_nlu(
            state=str(context.get("state") or ""),
            raw_text=message_text,
            pending_data=context.get("pending_data") or {},
        )
        if flow_nlu is not None:
            nlu_result = flow_nlu
        else:
            nlu_result = await nlu_engine.process(
                message_text,
                context,
                business_id,
                customer_context=customer_context_str,
            )

    nlu_result["_raw_user_text"] = message_text
    _apply_python_date_authority(nlu_result, message_text)
    intent = nlu_result.get("intent")
    confidence = nlu_result.get("confidence", 0)

    response_text: str | None = None

    interrupt_intents = {
        Intent.CHECK_APPOINTMENT.value,
        Intent.CANCEL_APPOINTMENT.value,
        Intent.MODIFY_APPOINTMENT.value,
    }
    if (
        current_intent == Intent.BOOK_APPOINTMENT.value
        and current_state != State.AWAITING_BOOKING_CONFIRMATION.value
        and intent in interrupt_intents
    ):
        if user_message_looks_like_booking_correction(message_text):
            intent = Intent.BOOK_APPOINTMENT.value
            nlu_result["intent"] = Intent.BOOK_APPOINTMENT.value
            iso = resolve_date_from_spanish_text(message_text)
            if iso:
                nlu_result.setdefault("entities", {})["date"] = iso
            dr = daypart_preference_hhmm_range(message_text)
            if dr:
                nlu_result.setdefault("entities", {})["time_daypart_range"] = {
                    "start": dr[0],
                    "end": dr[1],
                }
        else:
            await conversation_manager.clear_pending_data(business_id, user_key)
            current_state = State.IDLE.value
            current_intent = None

    if current_intent == Intent.BOOK_APPOINTMENT.value:
        if current_state == State.AWAITING_SLOT_SELECTION.value:
            pd = context.get("pending_data") or {}
            explicit_date = resolve_date_from_spanish_text(message_text)
            explicit_time = parse_time_candidates(message_text, allow_bare_hour=False)
            explicit_daypart = daypart_preference_hhmm_range(message_text)
            if explicit_date and explicit_date != pd.get("date"):
                response_text = await handle_book_appointment(nlu_result, context)
            elif explicit_daypart or explicit_time:
                response_text = await handle_book_appointment(nlu_result, context)
            else:
                response_text = await handle_slot_selection(nlu_result, context)
        elif current_state == State.AWAITING_BOOKING_CONFIRMATION.value:
            response_text = await handle_booking_confirmation(nlu_result, context)
        elif current_state in (
            State.AWAITING_SERVICE.value,
            State.AWAITING_DATE.value,
            State.AWAITING_TIME.value,
            State.AWAITING_NAME.value,
        ):
            response_text = await handle_book_appointment(nlu_result, context)

    elif current_intent == Intent.CANCEL_APPOINTMENT.value:
        if current_state in (
            State.AWAITING_CANCEL_CONFIRMATION.value,
            State.AWAITING_APPOINTMENT_SELECTION.value,
        ):
            response_text = await handle_cancel_appointment(nlu_result, context)

    elif current_intent == Intent.MODIFY_APPOINTMENT.value:
        if current_state in (
            State.AWAITING_APPOINTMENT_SELECTION_MODIFY.value,
            State.AWAITING_NEW_DATETIME.value,
            State.AWAITING_NEW_DATE.value,
            State.AWAITING_NEW_TIME.value,
            State.AWAITING_SLOT_SELECTION_MODIFY.value,
        ):
            response_text = await handle_modify_appointment(nlu_result, context)

    if response_text:
        await conversation_manager.save_message(
            business_id, user_key, "assistant", response_text
        )
        return response_text

    response_text = nlu_result.get("response_text", "")

    if not customer_id and intent != Intent.CLARIFICATION_NEEDED.value:
        if "nombre" in nlu_result.get("raw_understanding", "").lower() or context.get(
            "state"
        ) == State.AWAITING_NAME.value:
            customer_name = message_text.strip().title()
            if len(customer_name) > 2 and len(customer_name.split()) <= 4:
                result = await db_service.find_or_create_customer(
                    business_id, user_key, customer_name
                )
                customer = result["customer"]
                customer_id = customer["id"]
                await conversation_manager.set_customer_info(
                    business_id, user_key, customer_id, customer_name
                )
                await conversation_manager.update_context(
                    business_id, user_key, {"state": State.IDLE.value}
                )

    if confidence < config.CONFIDENCE_THRESHOLD:
        response_text = (
            "No estoy seguro de qué querés hacer. Elegí una opción:\n\n"
            f"{guided_menu(context.get('customer_name') or '')}"
        )
    elif intent == Intent.BOOK_APPOINTMENT.value:
        response_text = await handle_book_appointment(nlu_result, context)
    elif intent == Intent.CHECK_APPOINTMENT.value:
        response_text = await handle_check_appointment(nlu_result, context)
    elif intent == Intent.CANCEL_APPOINTMENT.value:
        response_text = await handle_cancel_appointment(nlu_result, context)
    elif intent == Intent.MODIFY_APPOINTMENT.value:
        response_text = await handle_modify_appointment(nlu_result, context)
    elif intent == Intent.BUSINESS_INFO.value:
        response_text = await handle_business_info(business_id)

    await conversation_manager.save_message(
        business_id, user_key, "assistant", response_text or ""
    )
    return response_text or EMPTY_REPLY_PLACEHOLDER
