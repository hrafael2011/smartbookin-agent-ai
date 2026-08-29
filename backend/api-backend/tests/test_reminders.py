"""Recordatorios de citas: ventanas de 24h y 2h (convenio wall-clock-as-UTC)."""
from datetime import datetime, timedelta, timezone

from app.services import background_tasks


NOW = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)


def test_reminder_windows_24h_and_2h():
    w = background_tasks._reminder_windows(NOW)
    assert w["start_24h"] == NOW + timedelta(hours=23, minutes=45)
    assert w["end_24h"] == NOW + timedelta(hours=24, minutes=15)
    assert w["start_2h"] == NOW + timedelta(hours=1, minutes=45)
    assert w["end_2h"] == NOW + timedelta(hours=2, minutes=15)
