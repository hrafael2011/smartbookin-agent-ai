"""F1/S10: get_availability no ofrece horarios ni fechas pasados."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import db_service


def _slot(hour, minute=0, day="2026-08-29"):
    return {
        "start_time": f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}",
        "start_datetime": f"{day}T{hour:02d}:{minute:02d}:00+00:00",
        "end_datetime": f"{day}T{hour:02d}:{(minute + 30) % 60:02d}:00+00:00",
    }


NOW = datetime(2026, 8, 29, 11, 46, tzinfo=timezone.utc)  # 11:46 AM operativo


def test_filter_past_slots_removes_same_day_past_slots():
    slots = [_slot(9, 15), _slot(11, 45), _slot(12, 0), _slot(15, 0)]
    kept = db_service._filter_past_slots(slots, now=NOW)
    assert [s["start_datetime"] for s in kept] == [
        "2026-08-29T12:00:00+00:00",
        "2026-08-29T15:00:00+00:00",
    ]


def test_filter_past_slots_keeps_future_days():
    slots = [_slot(9, 0, day="2026-08-30")]
    assert db_service._filter_past_slots(slots, now=NOW) == slots


def test_filter_past_slots_keeps_malformed_datetime():
    slots = [{"start_time": "9:00 AM", "start_datetime": "raro"}]
    assert db_service._filter_past_slots(slots, now=NOW) == slots


def test_filter_past_slots_excludes_exact_now():
    slots = [_slot(11, 46)]
    assert db_service._filter_past_slots(slots, now=NOW) == []


def test_get_availability_filters_past_slots(monkeypatch):
    raw_slots = [_slot(9, 15), _slot(15, 0)]
    monkeypatch.setattr(db_service, "build_slots", lambda *a, **k: raw_slots)
    monkeypatch.setattr(db_service, "_upcoming_now", lambda: NOW)

    class FakeResult:
        def scalars(self):
            return self

        def all(self):
            return []

        def first(self):
            return SimpleNamespace(duration_minutes=30, buffer_minutes=0)

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, query):
            return FakeResult()

    monkeypatch.setattr(db_service, "AsyncSessionLocal", lambda: FakeSession())

    result = asyncio.run(db_service.get_availability(1, 1, "2026-08-29"))
    assert [s["start_datetime"] for s in result["available_slots"]] == [
        "2026-08-29T15:00:00+00:00"
    ]
