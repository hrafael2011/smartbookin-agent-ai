"""Recordatorios de citas: ventanas de 24h y 2h (convenio wall-clock-as-UTC)."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services import background_tasks
from app.services import db_service


NOW = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)


def test_reminder_windows_24h_and_2h():
    w = background_tasks._reminder_windows(NOW)
    assert w["start_24h"] == NOW + timedelta(hours=23, minutes=45)
    assert w["end_24h"] == NOW + timedelta(hours=24, minutes=15)
    assert w["start_2h"] == NOW + timedelta(hours=1, minutes=45)
    assert w["end_2h"] == NOW + timedelta(hours=2, minutes=15)


class _Row:
    def __init__(self, appt_id=5, status="C", reminder_24h=False, reminder_2h=False, tg="tg:12345", service="Corte"):
        self.appointment = SimpleNamespace(
            id=appt_id, business_id=1, customer_id=7, service_id=1,
            date=NOW + timedelta(hours=23, minutes=50),  # dentro de la ventana 24h
            status=status, reminder_24h_sent=reminder_24h, reminder_2h_sent=reminder_2h,
        )
        self.customer = SimpleNamespace(phone_number=tg)
        self.service = SimpleNamespace(name=service)
        self.business = SimpleNamespace(name="Barbería La Excelencia", address="Calle 1")


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        # Un select(Appointment, Customer, Service, Business) real devuelve tuplas
        # de 4 entidades, como desempaqueta _send_window_reminders.
        return [(r.appointment, r.customer, r.service, r.business) for r in self._rows]


class FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.committed = False
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, query):
        self.executed.append(query)
        # La fila se "consume" tras el primer execute: en producción la ventana 2h
        # no devolvería una fila ya procesada (y marcada) por la ventana 24h.
        rows = self._rows
        self._rows = []
        return FakeResult(rows)

    async def commit(self):
        self.committed = True


def _run(rows, monkeypatch):
    sent = []
    session = FakeSession(rows)

    async def fake_send(chat_id, message, **kwargs):
        sent.append((chat_id, message))
        return {"ok": True}

    monkeypatch.setattr(background_tasks.db_service, "_upcoming_now", lambda: NOW)
    monkeypatch.setattr(background_tasks.telegram_client, "send_text_message", fake_send)
    monkeypatch.setattr(background_tasks, "AsyncSessionLocal", lambda: session)
    asyncio.run(background_tasks.process_appointment_reminders())
    return sent, session


def test_sends_24h_reminder_to_tg_chat(monkeypatch):
    sent, session = _run([_Row()], monkeypatch)
    assert len(sent) == 1
    chat_id, message = sent[0]
    assert chat_id == "12345"
    assert "Barbería La Excelencia" in message
    assert "Corte" in message
    assert session.committed is True


def test_marks_flag_only_on_successful_send(monkeypatch):
    sent, session = _run([_Row()], monkeypatch)
    assert sent and session.committed is True


def test_send_failure_does_not_mark_flag(monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("telegram down")

    session = FakeSession([_Row()])
    monkeypatch.setattr(background_tasks.db_service, "_upcoming_now", lambda: NOW)
    monkeypatch.setattr(background_tasks.telegram_client, "send_text_message", boom)
    monkeypatch.setattr(background_tasks, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(background_tasks.logger, "exception", lambda *a, **k: None)

    asyncio.run(background_tasks.process_appointment_reminders())

    assert session.committed is False


def test_non_tg_phone_is_skipped(monkeypatch):
    sent, session = _run([_Row(tg="8095550000")], monkeypatch)
    assert sent == []
    # Skip sin envío: no se marca flag ni se commitea (el flag queda libre por si
    # el cliente vincula Telegram más tarde).
    assert session.committed is False


def test_query_filters_windows_and_unset_flags(monkeypatch):
    from sqlalchemy.sql.elements import BindParameter

    session = FakeSession([])

    async def fake_send(*_a, **_k):
        return {"ok": True}

    monkeypatch.setattr(background_tasks.db_service, "_upcoming_now", lambda: NOW)
    monkeypatch.setattr(background_tasks.telegram_client, "send_text_message", fake_send)
    monkeypatch.setattr(background_tasks, "AsyncSessionLocal", lambda: session)

    asyncio.run(background_tasks.process_appointment_reminders())

    def _walk(clause):
        if isinstance(clause, BindParameter):
            value = clause.value
            if isinstance(value, (list, tuple)):
                yield from value
            else:
                yield value
        elif hasattr(clause, "get_children"):
            for c in clause.get_children():
                yield from _walk(c)

    values = list(_walk(session.executed[0].whereclause))
    assert NOW + timedelta(hours=23, minutes=45) in values
    assert NOW + timedelta(hours=24, minutes=15) in values
