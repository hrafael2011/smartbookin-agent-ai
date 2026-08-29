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
    def __init__(self, appt_id=5, status="C", reminder_24h=False, reminder_2h=False, tg="tg:12345", service="Corte", date=None):
        self.appointment = SimpleNamespace(
            id=appt_id, business_id=1, customer_id=7, service_id=1,
            date=date if date is not None else NOW + timedelta(hours=23, minutes=50),  # default: dentro de la ventana 24h
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
        # rows: lista plana de _Row (una sola pasada) o lista de listas (una por
        # execute, p. ej. [rows_24h, rows_2h]); cada lista se consume en su execute.
        if rows and isinstance(rows[0], list):
            self._passes = [list(r) for r in rows]
        else:
            self._passes = [list(rows)]
        self.committed = False
        self.rolled_back_nested = False
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, query):
        self.executed.append(query)
        rows = self._passes.pop(0) if self._passes else []
        return FakeResult(rows)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass

    def begin_nested(self):
        class _Nested:
            def __init__(self, session):
                self._session = session

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                if exc_type is not None:
                    self._session.rolled_back_nested = True
                return False

        return _Nested(self)


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
    row = _Row()
    sent, session = _run([row], monkeypatch)
    assert sent and session.committed is True
    assert row.appointment.reminder_24h_sent is True


def test_first_send_failure_does_not_break_second(monkeypatch):
    row1 = _Row(appt_id=1, tg="tg:11111")
    row2 = _Row(appt_id=2, tg="tg:22222")
    session = FakeSession([[row1, row2], []])
    sent = []

    async def fake_send(chat_id, message, **kwargs):
        if chat_id == "11111":
            raise RuntimeError("telegram down")
        sent.append((chat_id, message))
        return {"ok": True}

    monkeypatch.setattr(background_tasks.db_service, "_upcoming_now", lambda: NOW)
    monkeypatch.setattr(background_tasks.telegram_client, "send_text_message", fake_send)
    monkeypatch.setattr(background_tasks, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(background_tasks.logger, "exception", lambda *a, **k: None)

    asyncio.run(background_tasks.process_appointment_reminders())

    assert [c for c, _ in sent] == ["22222"]
    assert row2.appointment.reminder_24h_sent is True
    assert row1.appointment.reminder_24h_sent is False
    assert session.rolled_back_nested is True


def test_send_failure_does_not_mark_flag(monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("telegram down")

    row = _Row()
    session = FakeSession([row])
    monkeypatch.setattr(background_tasks.db_service, "_upcoming_now", lambda: NOW)
    monkeypatch.setattr(background_tasks.telegram_client, "send_text_message", boom)
    monkeypatch.setattr(background_tasks, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(background_tasks.logger, "exception", lambda *a, **k: None)

    asyncio.run(background_tasks.process_appointment_reminders())

    assert session.committed is False
    assert row.appointment.reminder_24h_sent is False


def test_non_tg_phone_is_skipped(monkeypatch):
    sent, session = _run([_Row(tg="8095550000")], monkeypatch)
    assert sent == []
    # Skip sin envío: no se marca flag ni se commitea (el flag queda libre por si
    # el cliente vincula Telegram más tarde).
    assert session.committed is False


def test_sends_2h_reminder_and_marks_flag(monkeypatch):
    row = _Row(date=NOW + timedelta(hours=1, minutes=50))  # dentro de la ventana 2h
    sent, session = _run([[], [row]], monkeypatch)
    assert len(sent) == 1
    chat_id, message = sent[0]
    assert chat_id == "12345"
    assert "Barbería La Excelencia" in message
    assert row.appointment.reminder_2h_sent is True
    assert session.committed is True


def test_query_filters_windows_and_unset_flags(monkeypatch):
    from sqlalchemy.sql.elements import BindParameter, False_, True_

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
        elif isinstance(clause, False_):
            yield False
        elif isinstance(clause, True_):
            yield True
        elif hasattr(clause, "get_children"):
            for c in clause.get_children():
                yield from _walk(c)

    values = list(_walk(session.executed[0].whereclause))
    assert NOW + timedelta(hours=23, minutes=45) in values
    assert NOW + timedelta(hours=24, minutes=15) in values
    assert False in values  # filtro flag == False (solo citas sin recordatorio previo)

    # La pasada 2h tiene sus propios bordes de ventana.
    values_2h = list(_walk(session.executed[1].whereclause))
    assert NOW + timedelta(hours=1, minutes=45) in values_2h
    assert NOW + timedelta(hours=2, minutes=15) in values_2h
    assert False in values_2h
