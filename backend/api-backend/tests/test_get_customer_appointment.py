"""RED: get_customer_appointment devuelve una cita del cliente con nombre de servicio."""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.services import db_service
from sqlalchemy.sql.elements import BindParameter


def test_get_customer_appointment_filters_by_customer(monkeypatch):
    captured = {}
    appt = {
        "id": 11,
        "service_id": 3,
        "service_name": "Corte",
        "start_at": "2026-08-28T09:00:00+00:00",
        "status": "C",
    }

    class FakeResult:
        def first(self):
            from types import SimpleNamespace
            appointment = SimpleNamespace(
                id=11, service_id=3,
                date=datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc),
                status="C",
            )
            service = SimpleNamespace(name="Corte")
            return (appointment, service)

    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def execute(self, query):
            captured["query"] = query
            return FakeResult()

    monkeypatch.setattr(db_service, "AsyncSessionLocal", lambda: FakeSession())

    result = asyncio.run(db_service.get_customer_appointment(11, customer_id=7))

    assert result["id"] == 11
    assert result["service_name"] == "Corte"
    # El query filtra por appointment_id Y customer_id
    def _walk(clause):
        if isinstance(clause, BindParameter):
            yield clause.value
        elif hasattr(clause, "get_children"):
            for c in clause.get_children():
                yield from _walk(c)
    values = list(_walk(captured["query"].whereclause))
    assert 11 in values
    assert 7 in values
