# Telegram Flujo Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir el flujo conversacional de Telegram: no ofrecer horarios pasados, solo botones (sin texto numerado), bloquear botones de mensajes anteriores con token por pantalla, y resolver los bugs silenciosos S1/S2/S3/S6/S10/S12/S16.

**Architecture:** Filtro de slots pasados en `get_availability()` (convenio wall-clock-as-UTC, `_upcoming_now()`); menú principal con texto corto sin numeración cuando hay teclado (`main_menu_reply`); token de pantalla opaco (`secrets.token_hex(4)`) rotado por cada mensaje con teclado en la capa de envío de Telegram y validado en el dispatch de callbacks; idempotencia por `callback_query.id`; logs en todos los excepts de handlers.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async + asyncpg, pytest (asyncio_mode=auto), Telegram Bot API.

**Spec:** `docs/superpowers/specs/2026-08-29-telegram-flujo-fixes-design.md`

**Base de trabajo:** `backend/api-backend/` (venv: `backend/api-backend/venv`). Comandos:
```bash
cd "/home/hendrick-rafael/Desktop/Proyectos Oficiales/appoinment-ai/backend/api-backend"
venv/bin/python -m pytest tests/ -q
```

---

### Task 1: F1 — Filtrar slots pasados en get_availability (cubre S10)

**Files:**
- Modify: `backend/api-backend/app/services/db_service.py`
- Test: `backend/api-backend/tests/test_past_slots_filter.py`

- [ ] **Step 1: Write the failing test**

```python
"""F1/S10: get_availability no ofrece horarios ni fechas pasados."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import db_service


def _slot(hour, minute=0, day="2026-08-29"):
    return {
        "start_time": f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}",
        "start_datetime": f"{day}T{hour:02d}:{minute:02d}:00+00:00",
        "end_datetime": f"{day}T{hour:02d}:{minute + 30:02d}:00+00:00",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_past_slots_filter.py -q`
Expected: FAIL — `AttributeError: module 'app.services.db_service' has no attribute '_filter_past_slots'`

- [ ] **Step 3: Implement `_filter_past_slots` y aplicarlo en `get_availability`**

En `db_service.py`, agregar (junto a `_upcoming_now`):

```python
def _filter_past_slots(slots: List[Dict], now: Optional[datetime] = None) -> List[Dict]:
    """Excluye slots cuya hora (wall-clock estampado como UTC) ya pasó."""
    now = now or _upcoming_now()
    kept = []
    for slot in slots:
        raw = str(slot.get("start_datetime") or "")
        try:
            start = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            kept.append(slot)
            continue
        if start > now:
            kept.append(slot)
    return kept
```

En `get_availability`, cambiar el return final:

```python
        return {"available_slots": _filter_past_slots(slots)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_past_slots_filter.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/services/db_service.py backend/api-backend/tests/test_past_slots_filter.py
git commit -m "fix(availability): no ofrecer slots ni fechas pasados (F1/S10)"
```

---

### Task 2: S2 — Guard de texto vacío en `_resolve_service_choice`

**Files:**
- Modify: `backend/api-backend/app/handlers/booking_handler.py:59-78`
- Test: `backend/api-backend/tests/test_booking_screens.py` (agregar tests)

- [ ] **Step 1: Write the failing tests** (agregar a `tests/test_booking_screens.py`)

```python
def test_resolve_service_choice_empty_text_returns_empty():
    services = [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]
    assert booking_handler._resolve_service_choice(services, "") == ""
    assert booking_handler._resolve_service_choice(services, "   ") == ""


def test_resolve_service_choice_still_matches_by_name_and_number():
    services = [
        {"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30},
        {"id": 2, "name": "Barba", "price": 8, "duration_minutes": 15},
    ]
    assert booking_handler._resolve_service_choice(services, "barba") == "Barba"
    assert booking_handler._resolve_service_choice(services, "2") == "Barba"


@pytest.mark.asyncio
async def test_booking_without_service_and_empty_text_asks_service(monkeypatch):
    """time_* callback sin servicio en pending → pregunta servicio, no confirma el primero."""
    captured = {}

    async def fake_services(_bid):
        return [
            {"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30},
            {"id": 2, "name": "Barba", "price": 8, "duration_minutes": 15},
        ]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

    nlu = {"_raw_user_text": "", "entities": {}, "missing": []}
    context = {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {"date": "2026-08-28", "selected_slot": _slot(hour=9), "service_id": 1},
    }
    reply = await booking_handler.handle_book_appointment(nlu, context)

    assert "¿Qué servicio" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["service_1", "service_2"]
    assert captured["update"]["state"] == "awaiting_service"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_booking_screens.py -q`
Expected: FAIL — `test_resolve_service_choice_empty_text_returns_empty` devuelve `"Corte"` en vez de `""` (y el flujo confirma el primer servicio).

- [ ] **Step 3: Implement el guard**

En `booking_handler._resolve_service_choice`, al inicio:

```python
def _resolve_service_choice(services: List[Dict], raw_text: str, entity_service: str = "") -> str:
    txt = str(raw_text or "").strip().lower()
    if not txt:
        return ""
    if txt.isdigit():
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_booking_screens.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/handlers/booking_handler.py backend/api-backend/tests/test_booking_screens.py
git commit -m "fix(booking): texto vacío no auto-selecciona el primer servicio (S2)"
```

---

### Task 3: F2a — Menú principal sin numeración cuando hay teclado

**Files:**
- Modify: `backend/api-backend/app/utils/telegram_ui.py`
- Modify: `backend/api-backend/app/services/guided_menu_router.py`
- Modify: `backend/api-backend/app/handlers/booking_handler.py`
- Modify: `backend/api-backend/app/handlers/cancel_handler.py`
- Modify: `backend/api-backend/app/handlers/modify_handler.py`
- Modify: `backend/api-backend/app/handlers/booking_calendar_handler.py`
- Modify: `backend/api-backend/tests/test_telegram_ui.py`, `tests/test_webhook_endpoints_ci.py`, `tests/test_ai_switch.py`, `tests/test_booking_calendar_flow.py`

- [ ] **Step 1: Write the failing tests** (agregar a `tests/test_telegram_ui.py`)

```python
def test_guided_menu_reply_has_no_numbered_options():
    reply = telegram_ui.guided_menu_reply("Ana")
    assert "1) Agendar cita" not in reply
    assert "Elegí una opción" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()


def test_main_menu_reply_with_prefix():
    reply = telegram_ui.main_menu_reply("Listo.", "Ana")
    assert reply.startswith("Listo.")
    assert "Elegí una opción" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_telegram_ui.py -q`
Expected: FAIL — `test_guided_menu_reply_has_no_numbered_options` (el texto actual tiene numeración).

- [ ] **Step 3: Implement en `telegram_ui.py`**

```python
def guided_menu_short(customer_name: str = "", *, returning: bool = False) -> str:
    """Texto del menú SIN numeración (para pantallas con teclado de botones)."""
    if returning and customer_name:
        lead = f"¡Bienvenido de nuevo, <b>{customer_name}</b>! 👋"
    elif customer_name:
        lead = f"¡Hola, <b>{customer_name}</b>! 👋"
    else:
        lead = "¡Hola! 👋"
    parts = [f"{lead}\n\n", "Elegí una opción:"]
    if config.ai_enabled:
        parts.append('\n\nTambién podés escribir tu pedido directo (ej. "quiero cita mañana 10am").')
    return "".join(parts)


def main_menu_reply(prefix: str = "", customer_name: str = "") -> BotReply:
    """Mensaje del menú principal (texto corto + teclado), con prefix opcional."""
    text = guided_menu_short(customer_name)
    if prefix:
        text = f"{prefix}\n\n{text}"
    return BotReply(text, keyboard=main_menu_keyboard())
```

Reemplazar `guided_menu_reply` por:

```python
def guided_menu_reply(customer_name: str = "") -> BotReply:
    """El menú principal como BotReply con su teclado (pantalla raíz, sin footer)."""
    return main_menu_reply(customer_name=customer_name)
```

(import de `config` ya existe en `telegram_ui.py`.)

- [ ] **Step 4: Run test to verify it passes + actualizar aserciones existentes**

Run: `venv/bin/python -m pytest tests/test_telegram_ui.py -q`
Expected: FAIL en `test_guided_menu_reply_is_bot_reply_with_main_menu_keyboard` (asserta "Agendar cita" en el texto). Actualizar esa aserción:

```python
def test_guided_menu_reply_is_bot_reply_with_main_menu_keyboard():
    reply = telegram_ui.guided_menu_reply("Ana")
    assert isinstance(reply, BotReply)
    assert "Ana" in reply
    assert "Elegí una opción" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
```

Run de nuevo: PASS.

- [ ] **Step 5: Migrar los sitios que devuelven menú con teclado**

En `guided_menu_router.py`:
- `_with_menu` → `return main_menu_reply(prefix, customer_name)`
- `_go_main_menu` → `return telegram_ui.main_menu_reply(customer_name=customer_name)`
- `show_menu` → `return telegram_ui.guided_menu_reply(customer_name)`
- `_stale_reply()` → `return telegram_ui.main_menu_reply("Esa opción ya no está vigente. Elegí del menú:")`
- `cancel_confirm` (no y yes) → `return telegram_ui.main_menu_reply(f"Entendido, tu cita se mantiene.\n\n{guided_menu(customer_name)}", customer_name)` **pero** quitando el `guided_menu(...)` del texto: `return telegram_ui.main_menu_reply("Entendido, tu cita se mantiene.", customer_name)` (el `f"Entendido...\n\n{guided_menu}"` pasa a solo el prefix).
- `resume` (no) → `telegram_ui.main_menu_reply("Entendido. Cerramos esa consulta.", customer_name)`

En `booking_handler.py` (confirmación exitosa): el texto final `f"...{guided_menu(customer_name)}"` pasa a:

```python
        return telegram_ui.main_menu_reply(
            "✅ ¡Tu cita está confirmada!\n\n"
            f"👤 {customer_name or 'Cliente'}\n"
            f"📅 {format_date_human_es(pending_data.get('date') or '')}\n"
            f"⏰ {selected_slot.get('start_time')}\n"
            f"✂️ {pending_data.get('service', 'servicio')}\n"
            f"📍 {business.get('name', '')}\n"
            f"    {business.get('address', '')}",
            customer_name,
        )
```

En `cancel_handler.py`: `return BotReply(f"Entendido, tu cita se mantiene.\n\n{guided_menu(customer_name)}", keyboard=...)` → `return telegram_ui.main_menu_reply("Entendido, tu cita se mantiene.", customer_name)`; igual para "✅ Tu cita ha sido cancelada exitosamente."

En `modify_handler.py`: `return BotReply(f"✅ ¡Listo! Tu cita se reagendó...{guided_menu(customer_name)}", keyboard=...)` → `return telegram_ui.main_menu_reply(<mismo prefix sin guided_menu>, customer_name)`.

En `booking_calendar_handler.py` (sin meses disponibles): `return BotReply("No encontré disponibilidad en los próximos 3 meses.\n\n" + guided_menu(...), keyboard=...)` → `return telegram_ui.main_menu_reply("No encontré disponibilidad en los próximos 3 meses.", context.get("customer_name") or "")`.

Nota: los handlers ya importan `telegram_ui`; `guided_menu` deja de usarse en esos puntos (quedan imports sin uso → limpiar si pytest/flake no los exige; el repo no usa flake8 en CI).

- [ ] **Step 6: Actualizar aserciones de tests que dependían del texto numerado**

- `tests/test_webhook_endpoints_ci.py:186` y `:315`: `assert "1) Agendar cita" in sent_messages[-1]` → `assert "Elegí una opción" in sent_messages[-1]`
- `tests/test_ai_switch.py:116`: `assert "1) Agendar cita" in text` → `assert "Elegí una opción" in text`
- `tests/test_ai_switch.py:154`: `assert "menú" in sent[0]` → revisar el contexto: si es el menú corto → `assert "Elegí una opción" in sent[0]`
- `tests/test_booking_calendar_flow.py:360`: `assert "menú" in response.lower() or "menu" in response.lower()` → `assert "Elegí una opción" in response`

Run: `venv/bin/python -m pytest tests/ -q` — resolver cualquier fallo residual de texto.

- [ ] **Step 7: Commit**

```bash
git add backend/api-backend/app/utils/telegram_ui.py backend/api-backend/app/services/guided_menu_router.py backend/api-backend/app/handlers/backend/api-backend/app/handlers/*.py backend/api-backend/tests/
git commit -m "feat(ui): menú principal sin numeración cuando hay teclado (F2)"
```

---

### Task 4: F2b — Catálogo de servicios con botones, check multi-cita, NO_SERVICES

**Files:**
- Modify: `backend/api-backend/app/handlers/business_info_handler.py`
- Modify: `backend/api-backend/app/handlers/check_handler.py`
- Modify: `backend/api-backend/app/services/no_services_nlu.py`
- Test: `backend/api-backend/tests/test_business_info_and_orchestrator_ui.py` (existe) + `tests/test_calendar_and_check_screens.py`

- [ ] **Step 1: Write the failing tests** (agregar a `tests/test_business_info_and_orchestrator_ui.py` y `tests/test_calendar_and_check_screens.py`)

```python
# tests/test_business_info_and_orchestrator_ui.py
import pytest
from app.core.response_builder import BotReply
from app.handlers import business_info_handler


@pytest.mark.asyncio
async def test_business_services_uses_buttons_not_numbers(monkeypatch):
    async def fake_services(_bid):
        return [
            {"id": 1, "name": "Corte", "price": 600, "duration_minutes": 30},
            {"id": 2, "name": "Cejas", "price": 100, "duration_minutes": 15},
        ]

    async def fake_business(_bid):
        return {"name": "Barbería"}

    monkeypatch.setattr(business_info_handler.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(business_info_handler.db_service, "get_business", fake_business)

    reply = await business_info_handler.handle_business_services(1)

    assert isinstance(reply, BotReply)
    assert "1. Corte" not in reply  # sin numeración en texto
    assert "Corte — $600" in reply   # info sin numeración
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["service_1", "service_2"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
```

```python
# tests/test_calendar_and_check_screens.py — agregar
@pytest.mark.asyncio
async def test_check_with_multiple_appointments_has_per_appointment_buttons(monkeypatch):
    async def fake_get(*_a, **_k):
        return [_appt(11, "2026-09-05T09:00:00+00:00", "Corte"), _appt(12, "2026-09-06T10:00:00+00:00", "Barba")]

    monkeypatch.setattr(check.db_service, "get_customer_appointments", fake_get)

    reply = await check.handle_check_appointment({}, _check_context())

    assert isinstance(reply, BotReply)
    # fila por cita: [modify_appt_<id>, cancel_appt_<id>]
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["modify_appt_11", "cancel_appt_11"]
    assert [b["callback_data"] for b in reply.keyboard[1]] == ["modify_appt_12", "cancel_appt_12"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
    assert "Solo dime cuál" not in reply
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_business_info_and_orchestrator_ui.py tests/test_calendar_and_check_screens.py -q`
Expected: FAIL (catálogo numerado / check sin botones por cita).

- [ ] **Step 3: Implement**

`business_info_handler.handle_business_services` → BotReply:

```python
async def handle_business_services(business_id: int) -> BotReply:
    services = await db_service.get_business_services(business_id)
    business = await db_service.get_business(business_id)
    bname = business.get("name", "el negocio")

    if not services:
        return BotReply(
            f"Por ahora <b>{bname}</b> no tiene servicios cargados en el sistema.\n\n"
            "Puedo ayudarte con horarios, ubicación o con otras consultas del negocio.",
            keyboard=telegram_ui.with_footer([]),
        )

    lines = [f"Estos son los servicios de <b>{bname}</b>:", ""]
    for s in services:
        lines.append(f"  • {s['name']} — ${s['price']}, {s['duration_minutes']} min")
    return BotReply(
        "\n".join(lines),
        keyboard=telegram_ui.with_footer(telegram_ui.service_buttons(services)),
    )
```

(imports: `from app.core.response_builder import BotReply`, `from app.utils import telegram_ui`.)

`check_handler.handle_check_appointment` — reemplazar el bloque de acciones:

```python
        visible = appointments[:5]
        action_rows = []
        for appt in visible:
            label = telegram_ui.short_appointment_label(appt)
            action_rows.append(
                [
                    {"text": f"✏️ {label}", "callback_data": f"modify_appt_{appt['id']}"},
                    {"text": f"❌ {label}", "callback_data": f"cancel_appt_{appt['id']}"},
                ]
            )
        return BotReply("\n".join(lines), keyboard=telegram_ui.with_footer(action_rows))
```

Y quitar la línea `lines.append("¿Quieres modificar o cancelar alguna? Solo dime cuál 😊")` del texto.

`no_services_nlu.py`: `"(opción 5)"` → `""` en `NO_SERVICES_GENERIC` y `GREETING_NO_SERVICES`:
`"Podés consultar horarios y ubicación en el menú, o contactar al local directamente."`

- [ ] **Step 4: Run tests to verify they pass + suite**

Run: `venv/bin/python -m pytest tests/test_business_info_and_orchestrator_ui.py tests/test_calendar_and_check_screens.py tests/test_ai_switch.py -q`
Expected: PASS. Luego suite completa: `venv/bin/python -m pytest tests/ -q` (si `test_ai_switch` u otros assertan el texto de NO_SERVICES, actualizar a la nueva redacción).

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/handlers/business_info_handler.py backend/api-backend/app/handlers/check_handler.py backend/api-backend/app/services/no_services_nlu.py backend/api-backend/tests/
git commit -m "feat(ui): catálogo con botones, check multi-cita con acciones, sin numeración (F2b/S6)"
```

---

### Task 5: F3a — Infraestructura de token en telegram_ui

**Files:**
- Modify: `backend/api-backend/app/utils/telegram_ui.py`
- Modify: `backend/api-backend/tests/test_telegram_ui.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_with_screen_token_suffixes_every_button():
    rows = [[{"text": "A", "callback_data": "service_1"}, {"text": "B", "callback_data": "service_2"}]]
    out = telegram_ui.with_screen_token(rows, "a1b2")
    assert out[0][0]["callback_data"] == "service_1|a1b2"
    assert out[0][1]["callback_data"] == "service_2|a1b2"


def test_parse_inline_callback_with_token():
    r = telegram_ui.parse_inline_callback("time_2026-08-29_09:00|a1b2")
    assert r["ns"] == "time"
    assert r["value"] == ("2026-08-29", "09:00")
    assert r["token"] == "a1b2"


def test_parse_inline_callback_without_token_has_none():
    r = telegram_ui.parse_inline_callback("nav_menu")
    assert r["token"] is None


def test_parse_inline_callback_rejects_token_only():
    assert telegram_ui.parse_inline_callback("|a1b2") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_telegram_ui.py -q`
Expected: FAIL (`AttributeError: with_screen_token` + assertions de `parse_inline_callback` que hoy no devuelven `token`).

- [ ] **Step 3: Implement en `telegram_ui.py`**

```python
def with_screen_token(rows: KeyboardRow, token: str) -> KeyboardRow:
    """Sufija `|token` a cada callback_data del teclado (token de pantalla)."""
    return [
        [{**btn, "callback_data": f"{btn['callback_data']}|{token}"} for btn in row]
        for row in rows
    ]


def split_callback_token(text: str):
    """Divide `base|token`; token es None si no hay sufijo."""
    if "|" in text:
        base, token = text.rsplit("|", 1)
        return base, token
    return text, None
```

`parse_inline_callback` — al inicio y en el retorno:

```python
def parse_inline_callback(text: str) -> Optional[Dict]:
    """Convierte un callback_data en ``{"ns", "value", "token"}`` o None.

    El token de pantalla (sufijo `|token`) se extrae antes de matchear; los
    callbacks tipeados sin token devuelven ``token=None``.
    """
    base, token = split_callback_token(str(text or ""))
    if not base:
        return None
    for ns, pattern in _CALLBACK_PATTERNS:
        m = pattern.match(base)
        ...
        return {"ns": ns, "value": value, "token": token}
    return None
```

- [ ] **Step 4: Actualizar aserciones existentes de `parse_inline_callback`**

En `tests/test_telegram_ui.py` y `tests/test_calendar_and_check_screens.py`, todas las aserciones de `parse_inline_callback(...) == {...}` deben incluir `"token": None` (ej. `assert telegram_ui.parse_inline_callback("service_3") == {"ns": "service", "value": "3", "token": None}`). Usar `replace_all` con el patrón por caso.

Run: `venv/bin/python -m pytest tests/test_telegram_ui.py tests/test_calendar_and_check_screens.py tests/test_inline_callbacks.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/utils/telegram_ui.py backend/api-backend/tests/
git commit -m "feat(callbacks): token de pantalla en callback_data (F3a)"
```

---

### Task 6: F3b — Rotación de token en el envío + validación en el dispatch

**Files:**
- Modify: `backend/api-backend/app/services/telegram_inbound.py`
- Modify: `backend/api-backend/app/services/guided_menu_router.py`
- Modify: `backend/api-backend/tests/test_inline_callbacks.py`
- Test: `backend/api-backend/tests/test_telegram_inbound_keyboards.py` (existe)

- [ ] **Step 1: Write the failing tests** (agregar a `tests/test_inline_callbacks.py`)

```python
@pytest.mark.asyncio
async def test_callback_with_old_token_is_blocked(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    decision = router.RouteDecision(
        "inline_callback",
        payload={"ns": "nav", "value": "menu", "token": "aaaa", "reason": "callback_nav"},
        reason="callback_nav",
    )
    reply = await router.execute_guided_route(
        1, "tg:1", decision, ctx(state="awaiting_service", screen_token="bbbb")
    )

    assert "ya no está vigente" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()


@pytest.mark.asyncio
async def test_callback_with_current_token_executes(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    decision = router.RouteDecision(
        "inline_callback",
        payload={"ns": "nav", "value": "menu", "token": "bbbb"},
        reason="callback_nav",
    )
    reply = await router.execute_guided_route(
        1, "tg:1", decision, ctx(state="awaiting_service", screen_token="bbbb")
    )

    assert reply.keyboard == telegram_ui.main_menu_keyboard()
    assert any(u.get("state") == "idle" for u in captured["updates"])


@pytest.mark.asyncio
async def test_callback_without_token_uses_state_validation(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    decision = router.RouteDecision(
        "inline_callback",
        payload={"ns": "confirm", "value": "yes", "token": None},
        reason="callback_confirm",
    )
    reply = await router.execute_guided_route(1, "tg:1", decision, ctx())  # idle

    assert "ya no está vigente" in reply  # estado no coincide (sin token)
```

Nota: el helper `cb(ns, value)` del archivo debe pasar `token=None` implícito (payload sin clave token → `payload.get("token")` → None). Los tests existentes siguen pasando sin cambios.

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_inline_callbacks.py -q`
Expected: FAIL — `test_callback_with_old_token_is_blocked` ejecuta el nav en vez de bloquear.

- [ ] **Step 3: Implement validación en `guided_menu_router._handle_inline_callback`**

Al inicio de `_handle_inline_callback`, antes de `_callback_valid_for_state`:

```python
    token = payload.get("token")
    if token is not None and token != context.get("screen_token"):
        await _clear_to_idle(business_id, user_key)
        await _mark_main_menu(business_id, user_key)
        return _stale_reply()
```

- [ ] **Step 4: Implement rotación de token en `telegram_inbound.py`**

Agregar helper y usarlo en los envíos del flujo guiado y NLU:

```python
async def _send_bot_reply(
    chat_id: str, business_id: int, user_key: str, reply
) -> Dict:
    """Envía un BotReply serializando el teclado y rotando el token de pantalla."""
    keyboard = getattr(reply, "keyboard", None)
    reply_markup = None
    if keyboard:
        token = secrets.token_hex(4)
        await conversation_manager.update_context(
            business_id, user_key, {"screen_token": token}
        )
        reply_markup = {"inline_keyboard": telegram_ui.with_screen_token(keyboard, token)}
    return await telegram_client.send_text_message(
        chat_id=chat_id, message=str(reply), reply_markup=reply_markup
    )
```

(imports: `import secrets` y `from app.utils import telegram_ui`.)

Reemplazar los envíos del flujo guiado (ambos sitios, guided y NLU) y el envío del menú de bienvenida en `_after_welcome_onboarding` y `_handle_telegram_display_name_capture` (donde haya teclado; los mensajes de texto puro siguen con `send_text_message`):

```python
            guided = await execute_guided_route(business_id, user_key, decision, ctx)
            if guided:
                ...
                await conversation_manager.save_message(business_id, user_key, "user", message_text)
                await conversation_manager.save_message(business_id, user_key, "assistant", guided)
                await _send_bot_reply(chat_id, business_id, user_key, guided)
                return {"status": "ok"}
```

y

```python
            response_text = await _run_nlu_pipeline(business_id, user_key, message_text)
            ...
            await _send_bot_reply(chat_id, business_id, user_key, response_text)
            return {"status": "ok"}
```

- [ ] **Step 5: Run tests to verify they pass + suite**

Run: `venv/bin/python -m pytest tests/test_inline_callbacks.py tests/test_telegram_inbound_keyboards.py -q`
Expected: PASS. Luego `venv/bin/python -m pytest tests/ -q` (los tests de webhook que mockean `send_text_message` siguen pasando porque `_send_bot_reply` llama a `telegram_client.send_text_message` con kwargs).

- [ ] **Step 6: Commit**

```bash
git add backend/api-backend/app/services/telegram_inbound.py backend/api-backend/app/services/guided_menu_router.py backend/api-backend/tests/
git commit -m "feat(callbacks): rotación y validación de token por pantalla (F3b)"
```

---

### Task 7: S1 — Idempotencia por toque + guard de callback sin message

**Files:**
- Modify: `backend/api-backend/app/services/telegram_client.py:113-126`
- Test: `backend/api-backend/tests/test_bot_reply_and_telegram_client.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_callback_query_uses_callback_id_for_dedupe():
    payload = {
        "callback_query": {
            "id": "123456789",
            "message": {"message_id": "99", "chat": {"id": "555"}, "date": 1700000000},
            "data": "service_1|a1b2",
        }
    }
    msg = telegram_client.extract_message_from_webhook(payload)
    assert msg["message_id"] == "123456789"  # id del toque, no del mensaje
    assert msg["button_payload"] == "service_1|a1b2"
    assert msg["from"] == "555"


def test_callback_query_without_message_is_ignored():
    payload = {"callback_query": {"id": "1", "data": "nav_menu"}}
    assert telegram_client.extract_message_from_webhook(payload) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_bot_reply_and_telegram_client.py -q`
Expected: FAIL — `test_callback_query_uses_callback_id_for_dedupe` devuelve `message_id == "99"`.

- [ ] **Step 3: Implement en `telegram_client.extract_message_from_webhook`**

Reemplazar el bloque `callback_query`:

```python
            if "callback_query" in payload:
                callback = payload["callback_query"]
                message = callback.get("message") or {}
                chat_id = str(message.get("chat", {}).get("id"))
                if not message or not chat_id or chat_id == "None":
                    logger.warning(
                        "telegram callback_query sin message/chat; ignorado (data=%s)",
                        (callback.get("data") or "")[:50],
                    )
                    return None
                return {
                    "message_id": str(callback.get("id")),  # único por toque (dedupe)
                    "from": chat_id,
                    "timestamp": str(message.get("date")),
                    "type": "interactive",
                    "button_payload": callback.get("data"),
                    "text": callback.get("data"),
                }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_bot_reply_and_telegram_client.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/services/telegram_client.py backend/api-backend/tests/test_bot_reply_and_telegram_client.py
git commit -m "fix(telegram): idempotencia por toque de callback y guard sin message (S1/S16)"
```

---

### Task 8: S3 — Logs en excepciones silenciosas

**Files:**
- Modify: `backend/api-backend/app/handlers/booking_handler.py`
- Modify: `backend/api-backend/app/handlers/cancel_handler.py`
- Modify: `backend/api-backend/app/handlers/check_handler.py`

- [ ] **Step 1: Write the failing tests** (agregar a `tests/test_booking_screens.py` y `tests/test_cancel_and_modify_screens.py`)

```python
@pytest.mark.asyncio
async def test_booking_confirmation_logs_exception(monkeypatch):
    captured = {}

    async def boom(*_a, **_k):
        raise RuntimeError("db down")

    async def fake_update(*_a, **_k):
        return None

    monkeypatch.setattr(booking_handler.db_service, "get_availability", boom)
    monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)
    monkeypatch.setattr(booking_handler.logger, "exception", lambda *a, **k: captured.setdefault("logged", True))

    nlu = {"_raw_user_text": "sí", "entities": {}, "missing": []}
    context = {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {"date": "2026-08-28", "service": "Corte", "service_id": 1, "selected_slot": _slot(hour=9)},
    }
    reply = await booking_handler.handle_booking_confirmation(nlu, context)

    assert "Hubo un problema" in reply
    assert captured.get("logged") is True
```

(análogo para cancel_handler y check_handler con sus funciones y su logger.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_booking_screens.py tests/test_cancel_and_modify_screens.py -q`
Expected: FAIL — `captured["logged"]` es None (no se loguea).

- [ ] **Step 3: Implement — agregar `logger.exception(...)` antes de cada return de error**

En `booking_handler.py` (2 excepts: consulta de disponibilidad y creación de cita):

```python
    except Exception as e:
        logger.exception("booking_availability_failed business=%s user=%s", business_id, phone_number)
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return f"Hubo un problema consultando la disponibilidad. ¿Podrías intentar de nuevo?"
```

```python
    except Exception:
        logger.exception("booking_create_failed business=%s user=%s customer=%s", business_id, phone_number, customer_id)
        await conversation_manager.clear_pending_data(business_id, phone_number)
        return "Hubo un problema creando la cita. Por favor intentá de nuevo."
```

En `cancel_handler.py` (except final):

```python
    except Exception as e:
        logger.exception("cancel_flow_failed business=%s user=%s customer=%s", business_id, phone_number, customer_id)
        return BotReply(...)
```

En `check_handler.py` (except):

```python
    except Exception as e:
        logger.exception("check_flow_failed business=%s user=%s customer=%s", business_id, phone_number, customer_id)
        return BotReply(...)
```

(verificar que cada módulo tenga `logger = logging.getLogger(__name__)`; agregar si falta en check_handler.)

- [ ] **Step 4: Run tests to verify they pass + suite**

Run: `venv/bin/python -m pytest tests/test_booking_screens.py tests/test_cancel_and_modify_screens.py -q` y luego `venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/handlers/booking_handler.py backend/api-backend/app/handlers/cancel_handler.py backend/api-backend/app/handlers/check_handler.py backend/api-backend/tests/
git commit -m "fix(logs): excepciones de handlers con logger.exception (S3)"
```

---

### Task 9: S12 — Paginación unificada (page_size=12)

**Files:**
- Modify: `backend/api-backend/app/handlers/booking_handler.py:26-38`
- Modify: `backend/api-backend/tests/test_booking_confirmation_flow.py:885-896`

- [ ] **Step 1: Write the failing test**

```python
def test_paginate_slots_uses_12_per_page():
    slots = [{"start_time": "10:00 AM", "start_datetime": f"2026-08-28T{10 + i:02d}:00:00+00:00"} for i in range(13)]
    page_info = booking_handler._paginate_slots(slots, page=0)
    assert len(page_info["slots"]) == 12
    assert page_info["has_next"] is True
    assert page_info["has_prev"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_booking_confirmation_flow.py -q`
Expected: FAIL — devuelve 6 por página (o el test de `_slots_short_list` con 7 slots falla por no tener "Siguiente").

- [ ] **Step 3: Implement — `_paginate_slots` delega en `telegram_ui.paginate_slots`**

```python
_SLOTS_PAGE_SIZE = 12


def _paginate_slots(slots: List[Dict], page: int, page_size: int = _SLOTS_PAGE_SIZE) -> Dict:
    return telegram_ui.paginate_slots(slots, page=page, page_size=page_size)
```

- [ ] **Step 4: Actualizar el test legacy de `_slots_short_list`**

En `tests/test_booking_confirmation_flow.py` (docstring "When slots > page_size..."): si el test crea ≤ 12 slots, cambiarlo a 13 slots para que siga mostrando "8) Siguiente →" con la nueva página de 12. Ajustar `slots = [ ... for i in range(13)]` y el índice del primer slot de la página 1 (`_SLOTS_PAGE_SIZE` = 12 ya funciona si hay ≥13 slots).

Run: `venv/bin/python -m pytest tests/test_booking_confirmation_flow.py tests/test_slots_reply.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api-backend/app/handlers/booking_handler.py backend/api-backend/tests/test_booking_confirmation_flow.py
git commit -m "refactor(pagination): tamaño de página unificado a 12 (S12)"
```

---

### Task 10: Documentación y suite completa

**Files:**
- Modify: `docs/TELEGRAM_UI_CONVENTION.md`
- Modify: `docs/superpowers/specs/2026-08-29-telegram-flujo-fixes-design.md` (marcar implementado, opcional)

- [ ] **Step 1: Actualizar `docs/TELEGRAM_UI_CONVENTION.md`**

- Sección "3. Convención de callback_data": agregar el sufijo de token —
  `callback_data = <ns>_<payload>|<token>`; el token es opaco (8 hex), rotado por
  cada mensaje con teclado, validado contra `context.screen_token`; los ids
  tipeados sin token usan validación por estado.
- Nueva sección "7. Horarios y fechas pasados": `get_availability` nunca ofrece
  slots con `start_datetime <= _upcoming_now()` (convenio wall-clock-as-UTC);
  aplica a cualquier día.
- Nota WhatsApp: los ids de WhatsApp usan la parte semántica (sin token); la
  validación de estado aplica igual.

- [ ] **Step 2: Correr la suite completa**

Run: `venv/bin/python -m pytest tests/ -q`
Expected: todos en verde (suite base 319 + nuevos tests de los Tasks 1-9).

- [ ] **Step 3: Verificar que no quedan textos numerados en pantallas con teclado**

Run: `grep -rn "1) Agendar cita\|9) Volver\|0) Menú principal\|X) Salir" backend/api-backend/app/ --include="*.py" | grep -v owner_`
Expected: sin resultados (los únicos textos numerados permitidos son `guided_menu()` — usado solo en caminos sin teclado/WhatsApp — y textos de owner).

- [ ] **Step 4: Commit**

```bash
git add docs/TELEGRAM_UI_CONVENTION.md
git commit -m "docs(ui): token de pantalla y filtro de horarios pasados en la convención"
```

- [ ] **Step 5: Push y alinear ramas** (dev y main)

```bash
git push origin main
git checkout smartbooking-agent-ai-dev && git merge --ff-only main && git push origin smartbooking-agent-ai-dev && git checkout main
```

---

## Self-review del plan vs spec

- **F1/S10** → Task 1 (filtro incondicional + tests). ✓
- **F2 menú** → Task 3 (guided_menu_short/main_menu_reply + migración de sitios + tests actualizados). ✓
- **F2 catálogo + S6 + NO_SERVICES** → Task 4. ✓
- **F3 token (infra + envío + validación)** → Tasks 5 y 6. ✓
- **S1/S16** → Task 7. ✓
- **S2** → Task 2. ✓
- **S3** → Task 8. ✓
- **S12** → Task 9. ✓
- **Docs + suite + push** → Task 10. ✓
