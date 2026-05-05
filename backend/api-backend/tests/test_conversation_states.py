from app.core.conversation_states import BOOKING_FLOW_STATES, State, is_known_state


def test_known_states():
    assert is_known_state(State.IDLE.value) is True
    assert is_known_state("not_a_real_state") is False


def test_calendar_booking_states_registered():
    assert is_known_state(State.BOOKING_CURRENT_WEEK.value) is True
    assert is_known_state(State.BOOKING_MONTH.value) is True
    assert is_known_state(State.BOOKING_WEEK.value) is True
    assert is_known_state(State.BOOKING_DAY.value) is True
    assert State.BOOKING_CURRENT_WEEK.value in BOOKING_FLOW_STATES
    assert State.BOOKING_MONTH.value in BOOKING_FLOW_STATES
    assert State.BOOKING_WEEK.value in BOOKING_FLOW_STATES
    assert State.BOOKING_DAY.value in BOOKING_FLOW_STATES
