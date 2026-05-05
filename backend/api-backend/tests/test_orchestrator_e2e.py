"""Orchestrator con dependencias mockeadas (sin LLM ni DB real)."""
import pytest

from app.core import orchestrator as orch
from app.core.conversation_states import Intent, State


@pytest.mark.asyncio
async def test_orchestrator_routes_to_check_handler(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.IDLE.value,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    async def fake_build_customer_context(*_a, **_k):
        return ""

    async def fake_nlu_process(*_a, **_k):
        return {
            "intent": Intent.CHECK_APPOINTMENT.value,
            "confidence": 1.0,
            "entities": {},
            "missing": [],
            "response_text": "",
            "raw_understanding": "test",
        }

    async def fake_check(_nlu, _ctx):
        return "CHECK_HANDLER_OK"

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch, "build_customer_context_for_nlu", fake_build_customer_context)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)
    monkeypatch.setattr(orch, "try_booking_flow_synthetic_nlu", lambda **kw: None)
    monkeypatch.setattr(orch, "handle_check_appointment", fake_check)

    out = await orch.run_conversation_turn(1, "w:99", "quiero ver mis citas")
    assert out == "CHECK_HANDLER_OK"


@pytest.mark.asyncio
async def test_orchestrator_confirmation_shortcut_skips_nlu(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.AWAITING_BOOKING_CONFIRMATION.value,
        "current_intent": Intent.BOOK_APPOINTMENT.value,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    called = {"nlu": 0}

    async def fake_nlu_process(*_a, **_k):
        called["nlu"] += 1
        return {"intent": "greeting", "confidence": 0.0, "entities": {}}

    async def fake_confirm(_nlu, _ctx):
        return "CONFIRM_OK"

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    async def noop_update(*_a, **_k):
        return None

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch.conversation_manager, "update_context", noop_update)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)
    monkeypatch.setattr(orch, "try_booking_flow_synthetic_nlu", lambda **kw: None)
    monkeypatch.setattr(orch, "handle_booking_confirmation", fake_confirm)
    monkeypatch.setattr(orch, "is_short_confirmation_message", lambda _t: True)

    out = await orch.run_conversation_turn(1, "w:99", "sí")
    assert out == "CONFIRM_OK"
    assert called["nlu"] == 0


@pytest.mark.asyncio
async def test_orchestrator_slot_selection_prefers_slot_handler_over_spurious_time_entity(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.AWAITING_SLOT_SELECTION.value,
        "current_intent": Intent.BOOK_APPOINTMENT.value,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {
            "date": "2026-04-14",
            "available_slots": [
                {"start_time": "9:00 AM", "start_datetime": "2026-04-14T09:00:00", "end_datetime": "2026-04-14T09:15:00"},
                {"start_time": "9:15 AM", "start_datetime": "2026-04-14T09:15:00", "end_datetime": "2026-04-14T09:30:00"},
            ],
        },
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    async def fake_build_customer_context(*_a, **_k):
        return ""

    async def fake_nlu_process(*_a, **_k):
        return {
            "intent": Intent.BOOK_APPOINTMENT.value,
            "confidence": 0.9,
            "entities": {"time": "04:00"},
            "missing": [],
            "response_text": "",
            "raw_understanding": "spurious_time_entity",
        }

    async def fake_slot(_nlu, _ctx):
        return "SLOT_HANDLER_OK"

    async def fake_book(_nlu, _ctx):
        return "BOOK_HANDLER_OK"

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    async def noop_update(*_a, **_k):
        return None

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch.conversation_manager, "update_context", noop_update)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch, "build_customer_context_for_nlu", fake_build_customer_context)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)
    monkeypatch.setattr(orch, "try_booking_flow_synthetic_nlu", lambda **kw: None)
    monkeypatch.setattr(orch, "handle_slot_selection", fake_slot)
    monkeypatch.setattr(orch, "handle_book_appointment", fake_book)

    out = await orch.run_conversation_turn(1, "w:99", "la opcion 4 me parece bien")
    assert out == "SLOT_HANDLER_OK"


@pytest.mark.asyncio
async def test_orchestrator_idle_menu_route_skips_nlu(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.IDLE.value,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    async def fake_nlu_process(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu route")

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)

    out = await orch.run_conversation_turn(1, "w:99", "puedes mostrarme el menu de inicio")
    assert "podés elegir una opción" in out.lower()


@pytest.mark.asyncio
async def test_orchestrator_idle_services_route_skips_nlu(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.IDLE.value,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    async def fake_nlu_process(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic services route")

    async def fake_get_services(_business_id):
        return [{"id": 1, "name": "Cejas", "price": 100, "duration_minutes": 15}]

    async def fake_get_business(_business_id):
        return {"name": "Barbería La Excelencia"}

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)
    monkeypatch.setattr(orch.db_service, "get_business_services", fake_get_services)
    monkeypatch.setattr(orch.db_service, "get_business", fake_get_business)

    out = await orch.run_conversation_turn(1, "w:99", "que servicios ofreces")
    assert "cejas" in out.lower()


@pytest.mark.asyncio
async def test_orchestrator_idle_cancel_route_uses_handler(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.IDLE.value,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    async def fake_nlu_process(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic cancel route")

    async def fake_cancel(_nlu, _ctx):
        return "CANCEL_HANDLER_OK"

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)
    monkeypatch.setattr(orch, "handle_cancel_appointment", fake_cancel)

    out = await orch.run_conversation_turn(1, "w:99", "como puedo cancelar una cita")
    assert out == "CANCEL_HANDLER_OK"


@pytest.mark.asyncio
async def test_orchestrator_idle_short_modify_word_routes(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.IDLE.value,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    async def fake_nlu_process(*_a, **_k):
        raise AssertionError("NLU should not run for short modify route")

    async def fake_modify(_nlu, _ctx):
        return "MODIFY_HANDLER_OK"

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)
    monkeypatch.setattr(orch, "handle_modify_appointment", fake_modify)

    out = await orch.run_conversation_turn(1, "w:99", "cambiar")
    assert out == "MODIFY_HANDLER_OK"


@pytest.mark.asyncio
async def test_orchestrator_low_confidence_returns_guided_menu(monkeypatch):
    base_ctx = {
        "business_id": 1,
        "phone_number": "w:99",
        "state": State.IDLE.value,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
    }

    async def save_msg(*_a, **_k):
        return None

    async def get_ctx(_bid, _uk):
        return dict(base_ctx)

    async def fake_build_customer_context(*_a, **_k):
        return ""

    async def fake_nlu_process(*_a, **_k):
        return {
            "intent": Intent.BOOK_APPOINTMENT.value,
            "confidence": 0.1,
            "entities": {},
            "missing": [],
            "response_text": "respuesta abierta del modelo",
            "raw_understanding": "low_confidence",
        }

    async def fail_book(*_a, **_k):
        raise AssertionError("Low confidence must not dispatch to mutation handlers")

    async def passthrough_coherent(bid, uk, ctx):
        return ctx

    monkeypatch.setattr(orch.conversation_manager, "save_message", save_msg)
    monkeypatch.setattr(orch.conversation_manager, "get_context", get_ctx)
    monkeypatch.setattr(orch, "ensure_coherent_context", passthrough_coherent)
    monkeypatch.setattr(orch, "build_customer_context_for_nlu", fake_build_customer_context)
    monkeypatch.setattr(orch.nlu_engine, "process", fake_nlu_process)
    monkeypatch.setattr(orch, "try_booking_flow_synthetic_nlu", lambda **kw: None)
    monkeypatch.setattr(orch, "handle_book_appointment", fail_book)

    out = await orch.run_conversation_turn(1, "w:99", "no se algo raro")

    assert "podés elegir una opción" in out.lower()
    assert "respuesta abierta del modelo" not in out
