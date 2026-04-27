import pytest

from app.core.conversation_states import Intent, State
from app.core import state_machine as sm
from app.services.conversation_manager import conversation_manager as cm_singleton


def test_required_intent_booking():
    assert sm.required_intent_for_flow_state(State.AWAITING_DATE.value) == Intent.BOOK_APPOINTMENT.value


def test_violation_when_cancel_intent_in_booking_state():
    assert (
        sm.context_intent_state_violation(
            Intent.CANCEL_APPOINTMENT.value,
            State.AWAITING_SERVICE.value,
        )
        is not None
    )


def test_no_violation_booking_pair():
    assert (
        sm.context_intent_state_violation(
            Intent.BOOK_APPOINTMENT.value,
            State.AWAITING_TIME.value,
        )
        is None
    )


def test_transition_rejects_cross_family():
    assert not sm.transition_allowed(
        State.AWAITING_SERVICE.value,
        State.AWAITING_APPOINTMENT_SELECTION.value,
        current_intent=Intent.BOOK_APPOINTMENT.value,
    )


def test_transition_allows_within_booking():
    assert sm.transition_allowed(
        State.AWAITING_SERVICE.value,
        State.AWAITING_DATE.value,
        current_intent=Intent.BOOK_APPOINTMENT.value,
    )


@pytest.mark.asyncio
async def test_ensure_coherent_calls_clear(monkeypatch):
    cleared = []

    async def fake_clear(bid, uk):
        cleared.append((bid, uk))

    async def fake_get_context(bid, uk):
        return {
            "business_id": bid,
            "phone_number": uk,
            "state": State.IDLE.value,
            "current_intent": None,
            "pending_data": {},
            "recent_messages": [],
        }

    monkeypatch.setattr(cm_singleton, "clear_pending_data", fake_clear)
    monkeypatch.setattr(cm_singleton, "get_context", fake_get_context)

    bad = {
        "state": State.AWAITING_SERVICE.value,
        "current_intent": Intent.MODIFY_APPOINTMENT.value,
        "pending_data": {},
    }
    out = await sm.ensure_coherent_context(9, "tg:x", bad)
    assert cleared == [(9, "tg:x")]
    assert out["state"] == State.IDLE.value
