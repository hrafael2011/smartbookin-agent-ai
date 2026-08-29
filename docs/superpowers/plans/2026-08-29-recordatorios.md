# Recordatorios de citas (24h y 2h) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar los recordatorios de citas (24h y 2h antes, precisión ±15 min) con el cron **dentro de Railway** (scheduler in-process del app), sin fragmentar la estructura.

**Architecture:** `process_appointment_reminders()` consulta citas activas (`P`/`C`) cuya fecha cae en la ventana 24h±15m o 2h±15m (comparando contra `db_service._upcoming_now()`, convenio wall-clock-as-UTC), envía por Telegram al chat del cliente y marca los flags `reminder_24h_sent`/`reminder_2h_sent` solo tras envío exitoso. El job APScheduler in-process ya registrado en main.py pasa de 30 a 15 min; se activa con `CRON_EXTERNAL=false` en Railway.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async + asyncpg, APScheduler, pytest (asyncio_mode=auto), Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-08-29-recordatorios-design.md`

**Base de trabajo:** `backend/api-backend/` (venv: `backend/api-backend/venv`).

---

### Task 1: Helper de ventanas `_reminder_windows`

**Files:**
- Modify: `backend/api-backend/app/services/background_tasks.py`
- Test: `backend/api-backend/tests/test_reminders.py` (nuevo)

- [ ] **Step 1: Write the failing test** (crear `tests/test_reminders.py`)

```python
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
```

- [ ] **Step 2: Run — verify FAIL** (`AttributeError: _reminder_windows`)

Run: `venv/bin/python -m pytest tests/test_reminders.py -q`

- [ ] **Step 3: Implement**

```python
REMINDER_CADENCE_MINUTES = 15


def _reminder_windows(now: datetime) -> dict:
    """Ventanas de 24h y 2h (ancho = cadencia ±15 min) en el convenio wall-clock-as-UTC."""
    return {
        "start_24h": now + timedelta(hours=23, minutes=60 - REMINDER_CADENCE_MINUTES),
        "end_24h": now + timedelta(hours=24, minutes=REMINDER_CADENCE_MINUTES),
        "start_2h": now + timedelta(hours=1, minutes=60 - REMINDER_CADENCE_MINUTES),
        "end_2h": now + timedelta(hours=2, minutes=REMINDER_CADENCE_MINUTES),
    }
```

- [ ] **Step 4: Run — PASS** (`venv/bin/python -m pytest tests/test_reminders.py -q`)

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/services/background_tasks.py backend/api-backend/tests/test_reminders.py
git commit -m "feat(reminders): ventanas de 24h y 2h con cadencia configurable"
```

---

### Task 2: `process_appointment_reminders()` real (query + envío + flags)

**Files:**
- Modify: `backend/api-backend/app/services/background_tasks.py`
- Modify: `backend/api-backend/app/services/db_service.py` (helper de consulta, si aplica)
- Test: `backend/api-backend/tests/test_reminders.py`

- [ ] **Step 1: Write the failing tests** (agregar a `tests/test_reminders.py`)

```python
import asyncio
from types import SimpleNamespace

from app.services import background_tasks
from app.services import db_service


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
        return self._rows


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
        return FakeResult(self._rows)

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
    monkeypatch.setattr(background_tasks.AsyncSessionLocal, "__call__", lambda: session)
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
    monkeypatch.setattr(background_tasks.AsyncSessionLocal, "__call__", lambda: session)
    monkeypatch.setattr(background_tasks.logger, "exception", lambda *a, **k: None)

    asyncio.run(background_tasks.process_appointment_reminders())

    assert session.committed is False


def test_non_tg_phone_is_skipped(monkeypatch):
    sent, session = _run([_Row(tg="8095550000")], monkeypatch)
    assert sent == []
    assert session.committed is True  # sin cambios que commitear
```

NOTA: el test `test_marks_flag_only_on_successful_send` valida el contrato de flags
por la vía del commit; la marcación exacta de `reminder_24h_sent` se valida con el
test de query (Task 2 Step 2) que inspecciona los binds de la ventana y el flag.

- [ ] **Step 2: Test de query (ventanas + flags en el whereclause)**

```python
def test_query_filters_windows_and_unset_flags(monkeypatch):
    from sqlalchemy.sql.elements import BindParameter

    session = FakeSession([])

    async def fake_send(*_a, **_k):
        return {"ok": True}

    monkeypatch.setattr(background_tasks.db_service, "_upcoming_now", lambda: NOW)
    monkeypatch.setattr(background_tasks.telegram_client, "send_text_message", fake_send)
    monkeypatch.setattr(background_tasks.AsyncSessionLocal, "__call__", lambda: session)

    asyncio.run(background_tasks.process_appointment_reminders())

    # El whereclause incluye los bordes de la ventana 24h
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
    assert False in values  # reminder_24h_sent = false (o el bind del flag)
```

- [ ] **Step 3: Run — verify FAIL** (el esqueleto no consulta ni envía)

- [ ] **Step 4: Implement** — reemplazar el cuerpo de `process_appointment_reminders()`:

```python
async def process_appointment_reminders():
    """Send 24h and 2h reminders (precisión ±15 min, convenio wall-clock-as-UTC)."""
    logger.info("Running appointment reminders job...")
    now = db_service._upcoming_now()
    windows = _reminder_windows(now)

    async with AsyncSessionLocal() as db:
        # 24h reminders
        await _send_window_reminders(db, windows["start_24h"], windows["end_24h"], "24h", "reminder_24h_sent", now)
        # 2h reminders
        await _send_window_reminders(db, windows["start_2h"], windows["end_2h"], "2h", "reminder_2h_sent", now)


async def _send_window_reminders(db, window_start, window_end, label, flag_attr, now):
    result = await db.execute(
        select(Appointment, Customer, Service, Business)
        .join(Customer, Appointment.customer_id == Customer.id, isouter=True)
        .join(Service, Appointment.service_id == Service.id, isouter=True)
        .join(Business, Appointment.business_id == Business.id, isouter=True)
        .filter(
            Appointment.status.in_(["P", "C"]),
            Appointment.date >= window_start,
            Appointment.date <= window_end,
            getattr(Appointment, flag_attr) == False,
        )
    )
    for appt, customer, service, business in result.all():
        phone = (customer.phone_number if customer else "") or ""
        if not phone.startswith("tg:"):
            logger.info("reminder_skip_non_tg business=%s appt=%s phone=%s", appt.business_id, appt.id, phone[:20])
            continue
        chat_id = phone[3:]
        message = (
            "📅 <b>Recordatorio de tu cita</b>\n\n"
            f"📍 {(business.name if business else '') or 'Negocio'}\n"
            f"✂️ {service.name if service else 'Servicio'}\n"
            f"📅 {appt.date.strftime('%A %d de %B')}\n"
            f"⏰ {appt.date.strftime('%I:%M %p').lstrip('0')}\n"
        )
        if business and business.address:
            message += f"    {business.address}\n"
        try:
            await telegram_client.send_text_message(chat_id=chat_id, message=message)
            setattr(appt, flag_attr, True)
            await db.commit()
            logger.info(
                "reminder_sent kind=%s appt=%s chat=%s business=%s",
                label, appt.id, chat_id, appt.business_id,
            )
        except Exception:
            logger.exception("reminder_send_failed kind=%s appt=%s chat=%s", label, appt.id, chat_id)
```

(imports necesarios: `from app.models import Appointment, Customer, Service, Business`,
`from app.services import db_service`, `from app.services.telegram_client import telegram_client`
— verificar qué importa ya el módulo y completar.)

- [ ] **Step 5: Run — PASS** (`venv/bin/python -m pytest tests/test_reminders.py -q`)

- [ ] **Step 6: Suite completa** `venv/bin/python -m pytest tests/ -q` — verde.

- [ ] **Step 7: Commit**

```bash
git add backend/api-backend/app/services/background_tasks.py backend/api-backend/tests/test_reminders.py
git commit -m "feat(reminders): envío de recordatorios 24h/2h con flags idempotentes"
```

---

### Task 3: Intervalo 15 min + docs + activación

**Files:**
- Modify: `backend/api-backend/main.py:61` (minutes=30 → 15)
- Modify: `backend/api-backend/.env.example` (comentario CRON_EXTERNAL)
- Modify: `docs/MVP_MIGRATION_PLAN.md` o `docs/TECH_DEBT.md` (nota de decisión)

- [ ] **Step 1: Cambiar el intervalo**

`main.py:61`: `scheduler.add_job(process_appointment_reminders, 'interval', minutes=15, id='reminders_job', replace_existing=True)`

- [ ] **Step 2: Actualizar `.env.example`**

Comentario de `CRON_EXTERNAL`:
```
# false (default): APScheduler in-process — recordatorios de citas cada 15 min.
# true: desactiva el scheduler (cron externo llama a /internal/jobs/*).
CRON_EXTERNAL=false
```

- [ ] **Step 3: Nota en docs**

En `docs/TECH_DEBT.md` (o MVP_MIGRATION_PLAN.md): "Decisión 2026-08-29: el cron de recordatorios corre **in-process** (APScheduler, 15 min) dentro del app always-on — sin servicios externos (se revierte la dirección de 'cron externo' de fase 4 por pedido del usuario, para no fragmentar la estructura)."

- [ ] **Step 4: Suite** `venv/bin/python -m pytest tests/ -q` — verde.

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/main.py backend/api-backend/.env.example docs/
git commit -m "feat(reminders): intervalo 15 min in-process + docs de activación"
```

---

### Task 4: Verificación final + push

- [ ] **Step 1: Suite completa** — `venv/bin/python -m pytest tests/ -q` (todo verde).
- [ ] **Step 2: Grep de sanity** — no quedan referencias al esqueleto (`"would go here"` en background_tasks.py).
- [ ] **Step 3: Commit + push + alinear ramas**

```bash
git push origin main
git checkout smartbooking-agent-ai-dev && git merge --ff-only main && git push origin smartbooking-agent-ai-dev && git checkout main
```

- [ ] **Step 4: Acción en Railway (dashboard, la hace el usuario)**: setear `CRON_EXTERNAL=false` en el servicio `smartbooking-ai` y redeployar. Verificación manual: agendar una cita para mañana a la misma hora → el bot envía el recordatorio ~24 h antes (o probar con `POST /internal/jobs/reminders` + token tras agendar una cita a ~23h50).

---

## Self-review del plan vs spec

- Lógica real + ventanas + convenio `_upcoming_now()` → Tasks 1-2. ✓
- Flags idempotentes solo tras envío exitoso → Task 2. ✓
- Precisión ±15 min (intervalo) → Task 3. ✓
- Cron dentro de Railway (in-process, sin fragmentar) → Task 3 (cambio de frecuencia) + Task 4 (CRON_EXTERNAL=false en Railway). ✓
- Docs y verificación → Tasks 3-4. ✓
- WhatsApp fuera de alcance → no implementado. ✓
