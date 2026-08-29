"""
Bug #1 (bloqueante): desincronización cita confirmada vs "ver mis citas".

El sistema guarda la hora local del negocio estampada como UTC (_utc_datetime):
una cita de 9:00 AM en Santo Domingo (UTC-4) queda en la BD como 09:00 UTC.
El filtro "upcoming" debe comparar contra el reloj OPERATIVO del negocio
(también estampado como UTC), no contra datetime.now() naive del servidor —
que en Railway (UTC) hacía que la cita del día quedara excluida de "próximas"
desde las 5:00 AM local, 4 horas antes de ocurrir.
"""
from datetime import date, datetime, time as dtime, timezone
from zoneinfo import ZoneInfo

from app.services import db_service
from app.utils.date_parse import DEFAULT_OPERATIONAL_TZ


class _Clock(datetime):
    """datetime con now() congelado, para aislar el reloj del servidor."""
    now_value: datetime = datetime(2026, 8, 28, 8, 55, tzinfo=DEFAULT_OPERATIONAL_TZ)

    @classmethod
    def now(cls, tz=None):
        return cls.now_value


def test_upcoming_now_stamps_operational_wallclock_as_utc(monkeypatch):
    """8:55 AM local del negocio se estampa como 08:55 UTC (no como 12:55 UTC real)."""
    monkeypatch.setattr(db_service, "datetime", _Clock)
    _Clock.now_value = datetime(2026, 8, 28, 8, 55, tzinfo=DEFAULT_OPERATIONAL_TZ)

    assert db_service._upcoming_now() == datetime(2026, 8, 28, 8, 55, tzinfo=timezone.utc)


def test_same_day_9am_appointment_visible_at_855am_local(monkeypatch):
    """Cita de hoy 9:00 AM local (guardada 09:00 UTC) es 'próxima' a las 8:55 AM local."""
    stored = db_service._utc_datetime(date(2026, 8, 28), dtime(9, 0))
    monkeypatch.setattr(db_service, "datetime", _Clock)
    _Clock.now_value = datetime(2026, 8, 28, 8, 55, tzinfo=DEFAULT_OPERATIONAL_TZ)

    assert stored >= db_service._upcoming_now()


def test_same_day_9am_appointment_hidden_after_905am_local(monkeypatch):
    """La misma cita deja de ser 'próxima' recién después de las 9:00 AM local (ya pasó)."""
    stored = db_service._utc_datetime(date(2026, 8, 28), dtime(9, 0))
    monkeypatch.setattr(db_service, "datetime", _Clock)
    _Clock.now_value = datetime(2026, 8, 28, 9, 5, tzinfo=DEFAULT_OPERATIONAL_TZ)

    assert not (stored >= db_service._upcoming_now())


def test_get_customer_appointments_uses_operational_now(monkeypatch):
    """El filtro upcoming de get_customer_appointments usa _upcoming_now(), no datetime.now()."""
    from sqlalchemy.sql.elements import BindParameter

    sentinel = datetime(2026, 8, 28, 8, 55, tzinfo=timezone.utc)
    monkeypatch.setattr(db_service, "_upcoming_now", lambda: sentinel)

    captured = {}

    class FakeResult:
        def all(self):
            return []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, query):
            captured["query"] = query
            return FakeResult()

    monkeypatch.setattr(db_service, "AsyncSessionLocal", lambda: FakeSession())

    import asyncio
    asyncio.run(db_service.get_customer_appointments(customer_id=7, upcoming=True))

    def _collect_bound(clause):
        out = []
        if isinstance(clause, BindParameter) and isinstance(clause.value, datetime):
            out.append(clause.value)
        elif hasattr(clause, "get_children"):
            for child in clause.get_children():
                out.extend(_collect_bound(child))
        return out

    bound = _collect_bound(captured["query"].whereclause)
    assert sentinel in bound


def test_upcoming_false_does_not_filter_by_date(monkeypatch):
    """upcoming=False no aplica el filtro de fecha (histórico completo)."""
    from sqlalchemy.sql.elements import BindParameter

    sentinel = datetime(2026, 8, 28, 8, 55, tzinfo=timezone.utc)
    monkeypatch.setattr(db_service, "_upcoming_now", lambda: sentinel)

    captured = {}

    class FakeResult:
        def all(self):
            return []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, query):
            captured["query"] = query
            return FakeResult()

    monkeypatch.setattr(db_service, "AsyncSessionLocal", lambda: FakeSession())

    import asyncio
    asyncio.run(db_service.get_customer_appointments(customer_id=7, upcoming=False))

    def _collect_bound(clause):
        out = []
        if isinstance(clause, BindParameter) and isinstance(clause.value, datetime):
            out.append(clause.value)
        elif hasattr(clause, "get_children"):
            for child in clause.get_children():
                out.extend(_collect_bound(child))
        return out

    where = captured["query"].whereclause
    if where is not None:
        assert sentinel not in _collect_bound(where)
