from app.core.conversation_states import State, is_known_state


def test_known_states():
    assert is_known_state(State.IDLE.value) is True
    assert is_known_state("not_a_real_state") is False
