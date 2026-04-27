"""
Validación de coherencia intent + estado (FSM) y reparación segura del contexto.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.conversation_states import (
    BOOKING_FLOW_STATES,
    CANCEL_FLOW_STATES,
    MODIFY_FLOW_STATES,
    Intent,
    State,
)

logger = logging.getLogger(__name__)


def required_intent_for_flow_state(state: str) -> Optional[str]:
    """Si el estado pertenece a un flujo activo, devuelve el current_intent exigido."""
    if state in BOOKING_FLOW_STATES:
        return Intent.BOOK_APPOINTMENT.value
    if state in CANCEL_FLOW_STATES:
        return Intent.CANCEL_APPOINTMENT.value
    if state in MODIFY_FLOW_STATES:
        return Intent.MODIFY_APPOINTMENT.value
    return None


def context_intent_state_violation(
    current_intent: Optional[str],
    state: str,
) -> Optional[str]:
    """
    None = contexto coherente.
    Si no, código de violación (para logs y tests).
    """
    if not state:
        return "empty_state"
    try:
        State(state)
    except ValueError:
        return f"unknown_state:{state}"

    if state in (State.IDLE.value, State.AWAITING_TELEGRAM_DISPLAY_NAME.value):
        return None

    required = required_intent_for_flow_state(state)
    if required is None:
        return None
    if current_intent != required:
        return f"intent_mismatch:state={state}:need={required}:got={current_intent}"
    return None


def transition_allowed(
    from_state: str,
    to_state: str,
    *,
    current_intent: Optional[str],
) -> bool:
    """
    Comprueba si un salto from_state → to_state es plausible.
    Rechaza saltos entre familias de flujo sin pasar por idle (p. ej. booking → cancel).
    """
    try:
        State(from_state)
        State(to_state)
    except ValueError:
        return False

    if from_state == to_state:
        return True

    req = required_intent_for_flow_state(from_state)
    if req is not None and current_intent != req:
        return False

    active_union = BOOKING_FLOW_STATES | CANCEL_FLOW_STATES | MODIFY_FLOW_STATES

    if from_state == State.IDLE.value:
        return to_state in active_union or to_state in (
            State.IDLE.value,
            State.AWAITING_TELEGRAM_DISPLAY_NAME.value,
        )

    if from_state in BOOKING_FLOW_STATES:
        if to_state in CANCEL_FLOW_STATES or to_state in MODIFY_FLOW_STATES:
            return False
        return to_state in BOOKING_FLOW_STATES or to_state == State.IDLE.value

    if from_state in CANCEL_FLOW_STATES:
        if to_state in BOOKING_FLOW_STATES or to_state in MODIFY_FLOW_STATES:
            return False
        return to_state in CANCEL_FLOW_STATES or to_state == State.IDLE.value

    if from_state in MODIFY_FLOW_STATES:
        if to_state in BOOKING_FLOW_STATES or to_state in CANCEL_FLOW_STATES:
            return False
        return to_state in MODIFY_FLOW_STATES or to_state == State.IDLE.value

    if from_state == State.AWAITING_TELEGRAM_DISPLAY_NAME.value:
        return to_state in (State.IDLE.value, State.AWAITING_TELEGRAM_DISPLAY_NAME.value)

    return to_state == State.IDLE.value


async def ensure_coherent_context(
    business_id: int,
    user_key: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Si intent y estado son incompatibles, resetea el flujo (clear_pending_data).
    """
    from app.services.conversation_manager import conversation_manager

    state = context.get("state") or State.IDLE.value
    intent = context.get("current_intent")
    viol = context_intent_state_violation(intent, state)
    if not viol:
        return context

    logger.warning(
        "fsm_repair business=%s user=%s violation=%s",
        business_id,
        user_key,
        viol,
    )
    await conversation_manager.clear_pending_data(business_id, user_key)
    return await conversation_manager.get_context(business_id, user_key)
