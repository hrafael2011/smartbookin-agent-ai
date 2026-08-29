"""
Pantallas de cancelar/modificar con citas reales como botones + confirmaciones con teclado.
"""
from importlib import import_module

import pytest

from app.core.response_builder import BotReply
from app.handlers import cancel_handler
from app.handlers import modify_handler
from app.utils import telegram_ui

cm_module = import_module("app.services.conversation_manager")

FOOTER = ["nav_back", "nav_menu", "nav_exit"]


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


def _slot_11():
    return {
        "start_time": "11:00 AM",
        "start_datetime": "2026-09-08T11:00:00+00:00",
        "end_datetime": "2026-09-08T11:30:00+00:00",
    }


def _ctx(customer_id=7, state="idle", **extra):
    base = {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": customer_id,
        "customer_name": "Ana",
        "state": state,
        "current_intent": None,
        "pending_data": {},
    }
    base.update(extra)
    return base


# ── Cancelar ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_without_appointments_offers_cta_and_footer(monkeypatch):
    async def fake_get(*_a, **_k):
        return []

    monkeypatch.setattr(cancel_handler.db_service, "get_customer_appointments", fake_get)

    reply = await cancel_handler.handle_cancel_appointment({}, _ctx())

    assert isinstance(reply, BotReply)
    assert "No tienes citas próximas para cancelar" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["menu_agendar"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_cancel_single_appointment_shows_confirm_buttons(monkeypatch):
    captured = {}

    async def fake_get(*_a, **_k):
        return [_appt()]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(cancel_handler.db_service, "get_customer_appointments", fake_get)
    monkeypatch.setattr(cancel_handler.conversation_manager, "update_context", fake_update)

    reply = await cancel_handler.handle_cancel_appointment({}, _ctx())

    assert isinstance(reply, BotReply)
    assert "¿Confirmás" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["cancel_confirm_yes", "cancel_confirm_no"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
    assert captured["update"]["state"] == "awaiting_cancel_confirmation"


@pytest.mark.asyncio
async def test_cancel_multiple_appointments_lists_real_ones_as_buttons(monkeypatch):
    captured = {}

    async def fake_get(*_a, **_k):
        return [_appt(11, "2026-09-05T09:00:00+00:00", "Corte"), _appt(12, "2026-09-06T10:00:00+00:00", "Barba")]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(cancel_handler.db_service, "get_customer_appointments", fake_get)
    monkeypatch.setattr(cancel_handler.conversation_manager, "update_context", fake_update)

    reply = await cancel_handler.handle_cancel_appointment({}, _ctx())

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "cancel_appt_11"
    assert reply.keyboard[1][0]["callback_data"] == "cancel_appt_12"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
    assert captured["update"]["state"] == "awaiting_appointment_selection"


@pytest.mark.asyncio
async def test_cancel_confirmation_yes_returns_main_menu_keyboard(monkeypatch):
    captured = {}

    async def fake_get(*_a, **_k):
        return [_appt()]

    async def fake_cancel(appointment_id, notes=None):
        captured["cancelled"] = appointment_id
        return True

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(cancel_handler.db_service, "get_customer_appointments", fake_get)
    monkeypatch.setattr(cancel_handler.db_service, "cancel_appointment", fake_cancel)
    monkeypatch.setattr(cancel_handler.conversation_manager, "update_context", fake_update)

    nlu = {"_raw_user_text": "sí"}
    reply = await cancel_handler.handle_cancel_appointment(
        nlu, _ctx(state="awaiting_cancel_confirmation", pending_data={"appointment_id": 11})
    )

    assert "cancelada exitosamente" in reply
    assert captured["cancelled"] == 11
    assert reply.keyboard == telegram_ui.main_menu_keyboard()


@pytest.mark.asyncio
async def test_cancel_handler_logs_exception(monkeypatch):
    captured = {}

    async def boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(cancel_handler.db_service, "get_customer_appointments", boom)
    monkeypatch.setattr(cancel_handler.logger, "exception", lambda *a, **k: captured.setdefault("logged", True))

    reply = await cancel_handler.handle_cancel_appointment({}, _ctx())

    assert "Hubo un problema" in reply
    assert captured.get("logged") is True


# ── Modificar ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_modify_without_appointments_offers_cta(monkeypatch):
    async def fake_get(*_a, **_k):
        return []

    monkeypatch.setattr(modify_handler.db_service, "get_customer_appointments", fake_get)

    reply = await modify_handler.handle_modify_appointment({}, _ctx())

    assert isinstance(reply, BotReply)
    assert "No tienes citas próximas para modificar" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["menu_agendar"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_modify_single_appointment_asks_new_date_with_day_buttons(monkeypatch):
    captured = {}

    async def fake_get(*_a, **_k):
        return [_appt()]

    async def fake_days(*_a, **_k):
        return [{"date": "2026-09-07", "label": "Lun 7"}]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(modify_handler.db_service, "get_customer_appointments", fake_get)
    monkeypatch.setattr(modify_handler.db_service, "get_available_days_in_range", fake_days)
    monkeypatch.setattr(modify_handler.conversation_manager, "update_context", fake_update)

    reply = await modify_handler.handle_modify_appointment({}, _ctx())

    assert isinstance(reply, BotReply)
    assert "¿Para cuándo" in reply
    assert reply.keyboard[0][0]["callback_data"] == "day_2026-09-07"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
    assert captured["update"]["state"] == "awaiting_new_datetime"


@pytest.mark.asyncio
async def test_modify_multiple_appointments_lists_real_ones_as_buttons(monkeypatch):
    captured = {}

    async def fake_get(*_a, **_k):
        return [_appt(11, "2026-09-05T09:00:00+00:00", "Corte"), _appt(12, "2026-09-06T10:00:00+00:00", "Barba")]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(modify_handler.db_service, "get_customer_appointments", fake_get)
    monkeypatch.setattr(modify_handler.conversation_manager, "update_context", fake_update)

    reply = await modify_handler.handle_modify_appointment({}, _ctx())

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "modify_appt_11"
    assert reply.keyboard[1][0]["callback_data"] == "modify_appt_12"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER
    assert captured["update"]["state"] == "awaiting_appointment_selection_modify"


@pytest.mark.asyncio
async def test_modify_slot_offer_uses_time_grid(monkeypatch):
    captured = {}

    async def fake_get(*_a, **_k):
        return [_appt()]

    async def fake_availability(**_kwargs):
        return {"available_slots": [{"start_time": "10:00 AM", "start_datetime": "2026-09-07T10:00:00+00:00"}]}

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(modify_handler.db_service, "get_customer_appointments", fake_get)
    monkeypatch.setattr(modify_handler.db_service, "get_availability", fake_availability)
    monkeypatch.setattr(modify_handler.conversation_manager, "update_context", fake_update)

    nlu = {"_raw_user_text": "", "entities": {"date": "2026-09-07", "time": "10:00 AM"}}
    context = _ctx(
        state="awaiting_new_datetime",
        current_intent="modify_appointment",
        pending_data={"selected_appointment_id": 11, "service_id": 1, "service_name": "Corte"},
    )
    reply = await modify_handler.handle_modify_appointment(nlu, context)

    assert isinstance(reply, BotReply)
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["time_2026-09-07_10:00"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == FOOTER


@pytest.mark.asyncio
async def test_modify_success_returns_main_menu_keyboard(monkeypatch):
    captured = {}

    async def fake_get(*_a, **_k):
        return [_appt()]

    async def fake_availability(**_kwargs):
        return {"available_slots": [_slot_11()]}

    async def fake_update_appt(appointment_id, update_data):
        captured["updated"] = (appointment_id, update_data)
        return {"id": 11}

    async def fake_update(*_a, **_k):
        return None

    async def fake_mark(*_a, **_k):
        captured["marked"] = True
        return None

    monkeypatch.setattr(modify_handler.db_service, "get_customer_appointments", fake_get)
    monkeypatch.setattr(modify_handler.db_service, "get_availability", fake_availability)
    monkeypatch.setattr(modify_handler.db_service, "update_appointment", fake_update_appt)
    monkeypatch.setattr(modify_handler.conversation_manager, "update_context", fake_update)
    monkeypatch.setattr(cm_module.conversation_manager, "mark_main_menu", fake_mark)

    nlu = {"_raw_user_text": "11:00 AM", "entities": {"time": "11:00 AM"}}
    context = _ctx(
        state="awaiting_slot_selection_modify",
        current_intent="modify_appointment",
        pending_data={
            "selected_appointment_id": 11,
            "service_id": 1,
            "service_name": "Corte",
            "new_date": "2026-09-08",
            "available_slots": [_slot_11()],
            "slot_page": 0,
        },
    )
    reply = await modify_handler.handle_modify_appointment(nlu, context)

    assert "se reagendó" in reply
    assert captured["updated"][0] == 11
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
    assert captured.get("marked") is True
