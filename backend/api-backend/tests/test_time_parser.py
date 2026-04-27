from app.utils.time_parser import parse_time_candidates, pick_exact_slot, sort_slots_by_requested_time


def test_parse_time_candidates_spanish_phrases():
    vals = parse_time_candidates("quiero a las 10 de la mañana")
    assert "10:00" in vals

    vals2 = parse_time_candidates("a las 3 de la tarde")
    assert "15:00" in vals2


def test_pick_exact_slot_by_requested_hour():
    slots = [
        {"start_datetime": "2026-04-10T09:00:00", "start_time": "9:00 AM"},
        {"start_datetime": "2026-04-10T10:00:00", "start_time": "10:00 AM"},
    ]
    slot = pick_exact_slot(slots, "10 de la mañana")
    assert slot is not None
    assert slot["start_time"] == "10:00 AM"


def test_sort_slots_by_requested_time_closest_first():
    slots = [
        {"start_datetime": "2026-04-10T09:00:00", "start_time": "9:00 AM"},
        {"start_datetime": "2026-04-10T11:00:00", "start_time": "11:00 AM"},
        {"start_datetime": "2026-04-10T10:30:00", "start_time": "10:30 AM"},
    ]
    ranked = sort_slots_by_requested_time(slots, "10:00 AM")
    assert ranked[0]["start_time"] == "10:30 AM"
