from datetime import datetime, timedelta, timezone

import pytest

from app.services.guided_menu_router import (
    ACTIVE_FLOW_TIMEOUT_SECONDS,
    RouteDecision,
    execute_guided_route,
    route_guided_message,
)


def ctx(state="idle", **extra):
    base = {
        "business_id": 1,
        "phone_number": "w:1",
        "state": state,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }
    base.update(extra)
    return base


@pytest.mark.parametrize(
    ("text", "kind", "uses_ai"),
    [
        ("hola", "show_menu", False),
        ("menu", "show_menu", False),
        ("help", "show_menu", False),
        ("1", "menu_option", False),
        ("5", "menu_option", False),
        ("que horario tienen", "business_info", False),
        ("cuanto cuesta un carro", "out_of_domain", False),
        ("esto es una mierda", "abusive", False),
        ("quiero cita mañana a las 10", "direct_shortcut", True),
    ],
)
def test_route_guided_message_idle_routes(text, kind, uses_ai):
    decision = route_guided_message(text, ctx())
    assert decision.kind == kind
    assert decision.uses_ai is uses_ai


def test_numeric_message_in_active_flow_is_not_global_menu():
    decision = route_guided_message("1", ctx(state="awaiting_slot_selection"))
    assert decision.kind == "active_flow"
    assert decision.option is None
    assert decision.uses_ai is False


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("0", "go_main_menu"),
        ("menu", "go_main_menu"),
        ("9", "go_back"),
        ("volver", "go_back"),
        ("x", "exit_flow"),
        ("salir", "exit_flow"),
    ],
)
def test_universal_navigation_in_active_flow(text, kind):
    decision = route_guided_message(text, ctx(state="awaiting_service"))
    assert decision.kind == kind
    assert decision.uses_ai is False


def test_active_flow_timeout_routes_to_expired_flow():
    old = datetime.now(timezone.utc) - timedelta(seconds=ACTIVE_FLOW_TIMEOUT_SECONDS + 5)
    decision = route_guided_message(
        "hola",
        ctx(state="awaiting_service", last_activity=old.isoformat()),
    )
    assert decision.kind == "expired_flow"
    assert decision.uses_ai is False


@pytest.mark.asyncio
async def test_execute_menu_option_one_starts_booking(monkeypatch):
    updates = []

    async def fake_services(_business_id):
        return [{"id": 1, "name": "Corte", "price": 500, "duration_minutes": 30}]

    async def fake_update(business_id, user_key, update):
        updates.append((business_id, user_key, update))

    monkeypatch.setattr(
        "app.services.guided_menu_router.db_service.get_business_services",
        fake_services,
    )
    monkeypatch.setattr(
        "app.services.guided_menu_router.conversation_manager.update_context",
        fake_update,
    )

    out = await execute_guided_route(1, "w:1", RouteDecision("menu_option", option="1"), ctx())
    assert "corte" in out.lower()
    assert updates[-1][2]["state"] == "awaiting_service"


@pytest.mark.asyncio
async def test_execute_menu_option_one_handles_no_services(monkeypatch):
    async def fake_services(_business_id):
        return []

    monkeypatch.setattr(
        "app.services.guided_menu_router.db_service.get_business_services",
        fake_services,
    )

    out = await execute_guided_route(1, "w:1", RouteDecision("menu_option", option="1"), ctx())

    assert "no tiene servicios" in out.lower()


@pytest.mark.asyncio
async def test_execute_business_info_does_not_invent_missing_schedule_or_location(monkeypatch):
    async def fake_business(_business_id):
        return {"name": "Demo", "address": "", "description": ""}

    async def fake_schedule(_business_id):
        return []

    monkeypatch.setattr(
        "app.handlers.business_info_handler.db_service.get_business",
        fake_business,
    )
    monkeypatch.setattr(
        "app.handlers.business_info_handler.db_service.get_business_schedule",
        fake_schedule,
    )

    out = await execute_guided_route(1, "w:1", RouteDecision("business_info"), ctx())

    assert "no hay horarios cargados" in out.lower()
    assert "dirección:" not in out.lower()


@pytest.mark.asyncio
async def test_execute_exit_flow_clears_transient_state(monkeypatch):
    updates = []

    async def fake_update(business_id, user_key, update):
        updates.append(update)

    monkeypatch.setattr(
        "app.services.guided_menu_router.conversation_manager.update_context",
        fake_update,
    )

    out = await execute_guided_route(1, "w:1", RouteDecision("exit_flow"), ctx(state="awaiting_service"))
    assert "cerré esta consulta" in out
    assert updates[-1] == {
        "current_intent": None,
        "pending_data": {},
        "state": "idle",
    }
