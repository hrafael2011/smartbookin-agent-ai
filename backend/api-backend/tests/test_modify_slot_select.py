from app.handlers.modify_handler import _select_modify_slot


def test_modify_slot_select_prefers_time_over_ambiguous_digit():
    slots = [
        {
            "start_time": "9:45 AM",
            "start_datetime": "2026-04-11T09:45:00",
            "end_datetime": "2026-04-11T10:15:00",
        },
        {
            "start_time": "12:00 PM",
            "start_datetime": "2026-04-11T12:00:00",
            "end_datetime": "2026-04-11T12:30:00",
        },
    ]
    picked = _select_modify_slot(slots, "12:00", "")
    assert picked is not None
    assert picked["start_time"] == "12:00 PM"


def test_modify_slot_select_no_false_match_when_requested_time_missing():
    slots = [
        {
            "start_time": "9:45 AM",
            "start_datetime": "2026-04-11T09:45:00",
            "end_datetime": "2026-04-11T10:15:00",
        },
    ]
    assert _select_modify_slot(slots, "12:00", "") is None
