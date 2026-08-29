"""
Pantallas del calendario (días/mes/semana) y de "ver mis citas" con teclados inline.
"""
import pytest

from app.core.response_builder import BotReply
from app.handlers import booking_calendar_handler as calendar
from app.handlers import check_handler as check
from app.utils import telegram_ui

FOOTER = ["nav_back", "nav_menu", "nav_exit"]


def _noop_update(monkeypatch, captured=None):
    async def fake_update(_b, _k, payload):
        if captured is not None:
            captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(calendar.conversation_manager, "update_context", fake_update)


# ── Calendario: semana actual ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_current_week_has_day_buttons_and_footer(monkeypatch):
    captured = {}

    async def fake_days(*_a, **_k):
        return [
            {"date": "2026-08-29", "label": "Vie 29"},
            {"date": "2026-08-30", "label": "Sáb 30"},
        ]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(calendar.db_service, "get_available_days_in_range", fake_days)
    monkeypatch.setattr(calendar.conversation_manager, "update_context", fake_update)

    reply = await calendar.handle_booking_current_week(
        1, "tg:1", 3, {"pending_data": {}, "customer_name": "Ana"}
    )

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "day_2026-08-29"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
    assert captured["updates"][-1]["state"] == "booking_current_week"


# ── Calendario: mes / semana / día ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_month_screen_has_month_buttons_and_footer(monkeypatch):
    captured = {}

    async def fake_days(*_a, **_k):
        return [{"date": "2026-09-02"}]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(calendar.db_service, "get_available_days_in_range", fake_days)
    monkeypatch.setattr(calendar.conversation_manager, "update_context", fake_update)

    reply = await calendar.handle_booking_month(
        1, "tg:1", {"pending_data": {"service_id": 3}, "customer_name": "Ana"}
    )

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "month_1"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_week_screen_has_week_buttons_and_footer(monkeypatch):
    captured = {}

    async def fake_days(*_a, **_k):
        return [{"date": "2026-09-03"}]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(calendar.db_service, "get_available_days_in_range", fake_days)
    monkeypatch.setattr(calendar.conversation_manager, "update_context", fake_update)

    context = {
        "pending_data": {
            "service_id": 3,
            "calendar_months": [{"index": 1, "year": 2026, "month": 9, "label": "Septiembre 2026"}],
        },
        "customer_name": "Ana",
    }
    reply = await calendar.handle_booking_week(1, "tg:1", 1, context)

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "week_1"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_day_screen_has_day_buttons_and_footer(monkeypatch):
    captured = {}

    async def fake_days(*_a, **_k):
        return [{"date": "2026-09-04", "label": "Vie 4"}]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(calendar.db_service, "get_available_days_in_range", fake_days)
    monkeypatch.setattr(calendar.conversation_manager, "update_context", fake_update)

    context = {
        "pending_data": {
            "service_id": 3,
            "calendar_weeks": [{"index": 1, "start": "2026-09-01", "end": "2026-09-07"}],
        },
        "customer_name": "Ana",
    }
    reply = await calendar.handle_booking_day(1, "tg:1", 1, context)

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "day_2026-09-04"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


def test_month_browse_callback_parses():
    assert telegram_ui.parse_inline_callback("month_browse") == {
        "ns": "month_browse",
        "value": "month_browse",
    }


# ── "Ver mis citas" ───────────────────────────────────────────────────────────

def _appt(appt_id=11, date_str="2026-09-05T09:00:00+00:00", service="Corte"):
    return {
        "id": appt_id,
        "service": 1,
        "service_name": service,
        "date": date_str[:10],
        "time": "9:00 AM",
        "start_at": date_str,
        "status": "C",
    }


def _check_context(appointments=None, customer_id=7):
    return {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": customer_id,
        "customer_name": "Ana",
    }


@pytest.mark.asyncio
async def test_check_without_appointments_offers_cta_and_footer(monkeypatch):
    async def fake_get(*_a, **_k):
        return []

    monkeypatch.setattr(check.db_service, "get_customer_appointments", fake_get)

    reply = await check.handle_check_appointment({}, _check_context())

    assert isinstance(reply, BotReply)
    assert "No tienes citas próximas" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["menu_agendar"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_check_without_customer_offers_cta(monkeypatch):
    reply = await check.handle_check_appointment({}, _check_context(customer_id=None))

    assert isinstance(reply, BotReply)
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["menu_agendar"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_check_with_appointments_lists_and_action_buttons(monkeypatch):
    async def fake_get(*_a, **_k):
        return [_appt()]

    monkeypatch.setattr(check.db_service, "get_customer_appointments", fake_get)

    reply = await check.handle_check_appointment({}, _check_context())

    assert isinstance(reply, BotReply)
    assert "Cita 1" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["modify_appt_11", "cancel_appt_11"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
