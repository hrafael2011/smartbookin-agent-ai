from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services import telegram_inbound
from app.services.owner_command_router import (
    OwnerRouteDecision,
    execute_owner_route,
    looks_like_owner_command,
    owner_menu,
    owner_user_key,
    route_owner_command,
)
from app.services.owner_read_models import (
    calculate_daily_metrics,
    format_agenda_response,
    format_appointment_detail,
    format_metrics_response,
)


def test_owner_menu_has_navigation_controls():
    text = owner_menu("Demo")

    assert "Panel rápido" in text
    assert "1) Agenda de hoy" in text
    assert "9) Volver" in text
    assert "0) Menú principal" in text
    assert "X) Salir" in text


def test_owner_route_maps_menu_navigation_and_shortcuts_without_ai():
    context = {"state": "idle"}

    assert route_owner_command("0", context) == OwnerRouteDecision(
        "show_menu", reason="main_menu"
    )
    assert route_owner_command("9", context) == OwnerRouteDecision(
        "go_back", reason="back"
    )
    assert route_owner_command("x", context) == OwnerRouteDecision(
        "exit_session", reason="exit"
    )
    assert route_owner_command("agenda de hoy", context) == OwnerRouteDecision(
        "menu_option", option="1", reason="today_agenda_shortcut"
    )
    assert route_owner_command("ganancias del dia", context).uses_ai is False


def test_owner_route_selects_appointment_detail_from_agenda_state():
    context = {"state": "owner_agenda_list", "pending_data": {"owner_agenda": [{"id": 1}]}}

    assert route_owner_command("1", context) == OwnerRouteDecision(
        "agenda_detail", option="1", reason="agenda_detail"
    )


def test_owner_route_expires_active_session_after_30_minutes():
    context = {
        "state": "viewing_agenda",
        "last_activity": (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(),
    }

    decision = route_owner_command("1", context)

    assert decision.kind == "expired_session"
    assert decision.reason == "owner_session_timeout"


def test_looks_like_owner_command_is_conservative():
    assert looks_like_owner_command("agenda de hoy") is True
    assert looks_like_owner_command("metricas") is True
    assert looks_like_owner_command("quiero una cita mañana") is False


def test_owner_read_models_format_empty_agenda():
    response = format_agenda_response("Agenda de hoy", [])

    assert "No hay citas registradas" in response
    assert "9) Volver" in response


def test_owner_metrics_calculation_handles_missing_price_and_statuses():
    metrics = calculate_daily_metrics(
        [
            {"status": "P", "price": 100},
            {"status": "C", "price": None},
            {"status": "D", "price": 250},
            {"status": "A", "price": 500},
        ]
    )

    assert metrics["total_appointments"] == 4
    assert metrics["pending"] == 1
    assert metrics["confirmed"] == 1
    assert metrics["completed"] == 1
    assert metrics["cancelled"] == 1
    assert metrics["estimated_revenue"] == 100
    assert metrics["realized_revenue"] == 250
    assert "Ingreso estimado: $100.00" in format_metrics_response("Métricas", metrics)


def test_owner_appointment_detail_format_includes_safe_fields():
    response = format_appointment_detail(
        {
            "appointment_id": 11,
            "local_time": "10:00 AM",
            "customer_name": "Ana",
            "customer_phone": "",
            "service_name": "Corte",
            "status_label": "confirmada",
            "price": 0,
        }
    )

    assert "Cita #11" in response
    assert "Teléfono: No registrado" in response
    assert "Precio: $0.00" in response


@pytest.mark.asyncio
async def test_execute_owner_route_exit_clears_owner_session(monkeypatch):
    updates = []

    async def fake_update_context(*args):
        updates.append(args)

    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        fake_update_context,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )

    response = await execute_owner_route(
        3,
        owner_user_key("123"),
        OwnerRouteDecision("exit_session", reason="exit"),
        {"state": "viewing_agenda"},
        owner_id=7,
        business_name="Demo",
    )

    assert "cerré el panel rápido" in response
    assert updates[-1][0] == 3
    assert updates[-1][1] == "owner:tg:123"
    assert updates[-1][2]["state"] == "idle"


@pytest.mark.asyncio
async def test_execute_owner_route_agenda_today_lists_read_model(monkeypatch):
    updates = []

    async def fake_list_owner_agenda(**kwargs):
        assert kwargs["owner_id"] == 7
        assert kwargs["business_id"] == 3
        return [
            {
                "appointment_id": 9,
                "local_time": "10:00 AM",
                "customer_name": "Ana",
                "customer_phone": "809",
                "service_name": "Corte",
                "status": "C",
                "status_label": "confirmada",
                "price": 300,
            }
        ]

    async def fake_update_context(*args):
        updates.append(args)

    monkeypatch.setattr(
        "app.services.owner_command_router.list_owner_agenda",
        fake_list_owner_agenda,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        fake_update_context,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )

    response = await execute_owner_route(
        3,
        owner_user_key("123"),
        OwnerRouteDecision("menu_option", option="1", reason="option_1"),
        {"state": "idle"},
        owner_id=7,
        business_name="Demo",
    )

    assert "Agenda de hoy" in response
    assert "Ana" in response
    assert updates[-1][2]["state"] == "owner_agenda_list"
    assert updates[-1][2]["pending_data"]["owner_agenda"][0]["appointment_id"] == 9


@pytest.mark.asyncio
async def test_execute_owner_route_agenda_detail_uses_cached_list(monkeypatch):
    updates = []

    async def fake_update_context(*args):
        updates.append(args)

    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        fake_update_context,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )

    response = await execute_owner_route(
        3,
        owner_user_key("123"),
        OwnerRouteDecision("agenda_detail", option="1", reason="agenda_detail"),
        {
            "state": "owner_agenda_list",
            "pending_data": {
                "owner_agenda": [
                    {
                        "appointment_id": 9,
                        "local_time": "10:00 AM",
                        "customer_name": "Ana",
                        "customer_phone": "809",
                        "service_name": "Corte",
                        "status_label": "confirmada",
                        "price": 300,
                    }
                ]
            },
        },
        owner_id=7,
        business_name="Demo",
    )

    assert "Cita #9" in response
    assert "Ana" in response
    assert updates[-1][2]["state"] == "owner_appointment_detail"


@pytest.mark.asyncio
async def test_execute_owner_route_back_from_detail_returns_previous_agenda(monkeypatch):
    updates = []

    async def fake_update_context(*args):
        updates.append(args)

    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        fake_update_context,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )

    response = await execute_owner_route(
        3,
        owner_user_key("123"),
        OwnerRouteDecision("go_back", reason="back"),
        {
            "state": "owner_appointment_detail",
            "pending_data": {
                "owner_agenda_kind": "upcoming",
                "owner_agenda": [
                    {
                        "appointment_id": 9,
                        "local_time": "10:00 AM",
                        "customer_name": "Ana",
                        "customer_phone": "809",
                        "service_name": "Corte",
                        "status_label": "confirmada",
                        "price": 300,
                    }
                ],
            },
        },
        owner_id=7,
        business_name="Demo",
    )

    assert "Próximas citas" in response
    assert "Ana" in response
    assert updates[-1][2]["state"] == "owner_agenda_list"


@pytest.mark.asyncio
async def test_telegram_bound_owner_routes_before_customer_binding(monkeypatch):
    sent = []

    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {"from": "123", "text": "menu", "message_id": "m-owner-1"},
    )

    async def fake_owner_binding(_telegram_user_id):
        return {"business_id": 3, "business_name": "Demo", "owner_id": 7}

    async def fail_customer_binding(_telegram_user_id):
        raise AssertionError("owner messages must not use customer binding")

    async def fake_should_process(*_args, **_kwargs):
        return True

    async def fake_get_context(*_args, **_kwargs):
        return {"state": "idle", "last_activity": datetime.now(timezone.utc).isoformat()}

    async def fake_update_context(*_args, **_kwargs):
        return None

    async def fake_save_message(*_args, **_kwargs):
        return None

    async def fake_send_text_message(*_args, **kwargs):
        sent.append(kwargs.get("message") or "")
        return {"ok": True}

    monkeypatch.setattr(telegram_inbound, "get_owner_binding_by_telegram_user_id", fake_owner_binding)
    monkeypatch.setattr(telegram_inbound, "get_binding_business_id", fail_customer_binding)
    monkeypatch.setattr(telegram_inbound, "should_process_channel_event", fake_should_process)
    monkeypatch.setattr(telegram_inbound.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(telegram_inbound.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(telegram_inbound.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(telegram_inbound.telegram_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )

    resp = await telegram_inbound.process_telegram_update({})

    assert resp.get("status") == "ok"
    assert "Panel rápido" in sent[-1]
    assert "Agenda de hoy" in sent[-1]


@pytest.mark.asyncio
async def test_telegram_unbound_owner_command_gets_activation_boundary(monkeypatch):
    sent = []

    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {"from": "123", "text": "agenda de hoy", "message_id": "m-owner-2"},
    )

    async def fake_owner_binding(_telegram_user_id):
        return None

    async def fake_customer_binding(_telegram_user_id):
        return None

    async def fake_send_text_message(*_args, **kwargs):
        sent.append(kwargs.get("message") or "")
        return {"ok": True}

    monkeypatch.setattr(telegram_inbound, "get_owner_binding_by_telegram_user_id", fake_owner_binding)
    monkeypatch.setattr(telegram_inbound, "get_binding_business_id", fake_customer_binding)
    monkeypatch.setattr(telegram_inbound.telegram_client, "send_text_message", fake_send_text_message)

    resp = await telegram_inbound.process_telegram_update({})

    assert resp.get("status") == "ok"
    assert "canal del dueño" in sent[-1]
    assert "vinculá este Telegram" in sent[-1]
