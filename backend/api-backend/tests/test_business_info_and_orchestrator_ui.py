"""
business_info_handler con footer + orchestrator mostrando menús con teclado.
"""
from importlib import import_module

import pytest

from app.core.response_builder import BotReply
from app.core.orchestrator import run_conversation_turn
from app.handlers import business_info_handler as info
from app.handlers.booking_calendar_handler import handle_booking_current_week
from app.utils import telegram_ui

FOOTER = ["nav_back", "nav_menu", "nav_exit"]


# ── Horarios y ubicación ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_business_info_has_footer(monkeypatch):
    async def fake_business(_bid):
        return {"name": "Barbería", "address": "Calle 1", "description": "Cortes"}

    async def fake_schedule(_bid):
        return [{"weekday": 4, "start_time": "09:00", "end_time": "18:00", "is_working_day": True}]

    monkeypatch.setattr(info.db_service, "get_business", fake_business)
    monkeypatch.setattr(info.db_service, "get_business_schedule", fake_schedule)

    reply = await info.handle_business_info(1)

    assert isinstance(reply, BotReply)
    assert "Barbería" in reply
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_business_services_has_cta_and_footer(monkeypatch):
    async def fake_services(_bid):
        return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

    async def fake_business(_bid):
        return {"name": "Barbería"}

    monkeypatch.setattr(info.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(info.db_service, "get_business", fake_business)

    reply = await info.handle_business_services(1)

    assert isinstance(reply, BotReply)
    assert "Corte" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["menu_agendar"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


# ── Orchestrator: menú con teclado ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idle_menu_returns_main_menu_keyboard(monkeypatch):
    captured = {}

    async def fake_get_context(_bid, _user):
        return {"state": "idle", "current_intent": None, "customer_name": "Ana", "recent_messages": []}

    async def fake_save(*_a, **_k):
        return None

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(run_conversation_turn.__globals__["conversation_manager"], "get_context", fake_get_context)
    monkeypatch.setattr(run_conversation_turn.__globals__["conversation_manager"], "save_message", fake_save)
    monkeypatch.setattr(run_conversation_turn.__globals__["conversation_manager"], "update_context", fake_update)

    reply = await run_conversation_turn(1, "tg:1", "menu")

    assert isinstance(reply, BotReply)
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
    assert any(u.get("last_screen") == "main_menu" for u in captured["updates"])


@pytest.mark.asyncio
async def test_calendar_back_returns_footer_reply(monkeypatch):
    captured = {}

    async def fake_days(*_a, **_k):
        return []

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(handle_booking_current_week.__globals__["db_service"], "get_available_days_in_range", fake_days)
    monkeypatch.setattr(handle_booking_current_week.__globals__["conversation_manager"], "update_context", fake_update)

    from app.core.orchestrator import _calendar_back

    reply = await _calendar_back(
        1, "tg:1", {"state_stack": ["booking_current_week"], "customer_name": "Ana"}
    )

    assert "Volvemos" in reply
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
    assert captured["update"]["state"] == "booking_current_week"
