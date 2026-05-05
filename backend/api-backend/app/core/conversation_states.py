"""
Estados e intenciones del flujo conversacional (state machine declarativa).
Los handlers persisten el siguiente estado en ConversationState (PostgreSQL).
"""
from __future__ import annotations

from enum import Enum
from typing import FrozenSet


class Intent(str, Enum):
    BOOK_APPOINTMENT = "book_appointment"
    CHECK_APPOINTMENT = "check_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    MODIFY_APPOINTMENT = "modify_appointment"
    BUSINESS_INFO = "business_info"
    GREETING = "greeting"
    GENERAL_QUESTION = "general_question"
    CLARIFICATION_NEEDED = "clarification_needed"


class State(str, Enum):
    IDLE = "idle"
    AWAITING_SERVICE = "awaiting_service"
    AWAITING_DATE = "awaiting_date"
    AWAITING_TIME = "awaiting_time"
    AWAITING_NAME = "awaiting_name"
    AWAITING_SLOT_SELECTION = "awaiting_slot_selection"
    AWAITING_BOOKING_CONFIRMATION = "awaiting_booking_confirmation"
    AWAITING_TELEGRAM_DISPLAY_NAME = "awaiting_telegram_display_name"
    AWAITING_APPOINTMENT_SELECTION = "awaiting_appointment_selection"
    AWAITING_CANCEL_CONFIRMATION = "awaiting_cancel_confirmation"
    AWAITING_APPOINTMENT_SELECTION_MODIFY = "awaiting_appointment_selection_modify"
    AWAITING_NEW_DATETIME = "awaiting_new_datetime"
    AWAITING_NEW_DATE = "awaiting_new_date"
    AWAITING_NEW_TIME = "awaiting_new_time"
    AWAITING_SLOT_SELECTION_MODIFY = "awaiting_slot_selection_modify"
    AWAITING_SESSION_RESUME = "awaiting_session_resume"
    BOOKING_CURRENT_WEEK = "booking_current_week"
    BOOKING_MONTH = "booking_month"
    BOOKING_WEEK = "booking_week"
    BOOKING_DAY = "booking_day"


BOOKING_FLOW_STATES: FrozenSet[str] = frozenset(
    {
        State.AWAITING_SERVICE.value,
        State.AWAITING_DATE.value,
        State.AWAITING_TIME.value,
        State.AWAITING_NAME.value,
        State.BOOKING_CURRENT_WEEK.value,
        State.BOOKING_MONTH.value,
        State.BOOKING_WEEK.value,
        State.BOOKING_DAY.value,
        State.AWAITING_SLOT_SELECTION.value,
        State.AWAITING_BOOKING_CONFIRMATION.value,
    }
)

CANCEL_FLOW_STATES: FrozenSet[str] = frozenset(
    {
        State.AWAITING_APPOINTMENT_SELECTION.value,
        State.AWAITING_CANCEL_CONFIRMATION.value,
    }
)

MODIFY_FLOW_STATES: FrozenSet[str] = frozenset(
    {
        State.AWAITING_APPOINTMENT_SELECTION_MODIFY.value,
        State.AWAITING_NEW_DATETIME.value,
        State.AWAITING_NEW_DATE.value,
        State.AWAITING_NEW_TIME.value,
        State.AWAITING_SLOT_SELECTION_MODIFY.value,
    }
)


def is_known_state(value: str) -> bool:
    try:
        State(value)
        return True
    except ValueError:
        return False
