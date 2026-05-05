"""Tests for owner-channel mutating actions: cancel, complete, reschedule, block, notifications."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.owner_command_router import (
    OwnerRouteDecision,
    execute_owner_route,
    owner_menu,
    owner_user_key,
    route_owner_command,
)
from app.services.owner_mutations import MutationResult
from app.services.owner_read_models import format_appointment_detail


# ── Menu structure ─────────────────────────────────────────────────────────────

def test_menu_has_six_options_including_block():
    text = owner_menu("Demo")
    assert "5) Notificaciones" in text
    assert "6) Bloquear horario" in text


# ── Routing: action keys from detail view ──────────────────────────────────────

def test_route_c_from_detail_returns_action_cancel():
    context = {"state": "owner_appointment_detail"}
    assert route_owner_command("c", context) == OwnerRouteDecision("action_cancel", reason="cancel_from_detail")


def test_route_m_from_detail_returns_action_complete():
    context = {"state": "owner_appointment_detail"}
    assert route_owner_command("m", context) == OwnerRouteDecision("action_complete", reason="complete_from_detail")


def test_route_r_from_detail_returns_action_reschedule():
    context = {"state": "owner_appointment_detail"}
    assert route_owner_command("r", context) == OwnerRouteDecision("action_reschedule", reason="reschedule_from_detail")


def test_route_6_returns_block_option():
    context = {"state": "idle"}
    assert route_owner_command("6", context) == OwnerRouteDecision("menu_option", option="6", reason="option_6")


def test_route_notifications_shortcut():
    context = {"state": "idle"}
    d = route_owner_command("notificaciones", context)
    assert d.kind == "menu_option"
    assert d.option == "5"


def test_route_block_shortcut():
    context = {"state": "idle"}
    d = route_owner_command("bloquear horario", context)
    assert d.kind == "menu_option"
    assert d.option == "6"


# ── Flow states return flow_input ──────────────────────────────────────────────

@pytest.mark.parametrize("state", [
    "owner_cancel_confirm",
    "owner_complete_confirm",
    "owner_reschedule_ask_date",
    "owner_reschedule_slots",
    "owner_reschedule_confirm",
    "owner_block_ask_date",
    "owner_block_ask_start",
    "owner_block_ask_end",
    "owner_block_confirm",
])
def test_flow_states_route_as_flow_input(state):
    context = {"state": state}
    d = route_owner_command("cualquier texto", context)
    assert d.kind == "flow_input"


# ── format_appointment_detail shows actions only for active statuses ───────────

def test_detail_shows_actions_for_pending():
    item = _make_item(status="P")
    text = format_appointment_detail(item)
    assert "C) Cancelar" in text
    assert "M) Marcar como completada" in text
    assert "R) Reagendar" in text


def test_detail_shows_actions_for_confirmed():
    item = _make_item(status="C")
    text = format_appointment_detail(item)
    assert "C) Cancelar" in text


def test_detail_no_actions_for_cancelled():
    item = _make_item(status="A")
    text = format_appointment_detail(item)
    assert "C) Cancelar" not in text
    assert "M) Marcar como completada" not in text


def test_detail_no_actions_for_completed():
    item = _make_item(status="D")
    text = format_appointment_detail(item)
    assert "C) Cancelar" not in text


# ── Cancel flow ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_flow_shows_confirmation(monkeypatch):
    _patch_ctx(monkeypatch)
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("action_cancel", reason="cancel_from_detail"),
        _ctx_with_item(status="C"),
        owner_id=1, business_name="Demo",
    )
    assert "cancelar" in response.lower()
    assert "Respondé" in response or "respondé" in response.lower()


@pytest.mark.asyncio
async def test_cancel_flow_yes_calls_mutation(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_cancel = AsyncMock(return_value=MutationResult(ok=True))
    monkeypatch.setattr("app.services.owner_command_router.owner_cancel_appointment", mock_cancel)

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_cancel_confirm"),
        _ctx_with_item(status="C", state="owner_cancel_confirm"),
        owner_id=1, business_name="Demo",
    )
    mock_cancel.assert_called_once()
    assert "cancelada" in response.lower()


@pytest.mark.asyncio
async def test_cancel_flow_no_returns_detail(monkeypatch):
    _patch_ctx(monkeypatch)
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="no", reason="flow_owner_cancel_confirm"),
        _ctx_with_item(status="C", state="owner_cancel_confirm"),
        owner_id=1, business_name="Demo",
    )
    assert "Cita #" in response


@pytest.mark.asyncio
async def test_cancel_flow_not_cancellable_shows_error(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_cancel = AsyncMock(return_value=MutationResult(ok=False, error="not_cancellable"))
    monkeypatch.setattr("app.services.owner_command_router.owner_cancel_appointment", mock_cancel)

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_cancel_confirm"),
        _ctx_with_item(status="A", state="owner_cancel_confirm"),
        owner_id=1, business_name="Demo",
    )
    assert "no se puede cancelar" in response.lower()


# ── Complete flow ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_flow_shows_confirmation(monkeypatch):
    _patch_ctx(monkeypatch)
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("action_complete", reason="complete_from_detail"),
        _ctx_with_item(status="P"),
        owner_id=1, business_name="Demo",
    )
    assert "completada" in response.lower()


@pytest.mark.asyncio
async def test_complete_does_not_apply_to_cancelled(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_complete = AsyncMock(return_value=MutationResult(ok=False, error="not_completable"))
    monkeypatch.setattr("app.services.owner_command_router.owner_complete_appointment", mock_complete)

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_complete_confirm"),
        _ctx_with_item(status="A", state="owner_complete_confirm"),
        owner_id=1, business_name="Demo",
    )
    assert "no se puede marcar" in response.lower()


@pytest.mark.asyncio
async def test_complete_flow_yes_calls_mutation(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_complete = AsyncMock(return_value=MutationResult(ok=True))
    monkeypatch.setattr("app.services.owner_command_router.owner_complete_appointment", mock_complete)

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_complete_confirm"),
        _ctx_with_item(status="P", state="owner_complete_confirm"),
        owner_id=1, business_name="Demo",
    )
    mock_complete.assert_called_once()
    assert "completada" in response.lower()


# ── Reschedule flow ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reschedule_action_asks_for_date(monkeypatch):
    _patch_ctx(monkeypatch)
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("action_reschedule", reason="reschedule_from_detail"),
        _ctx_with_item(status="P"),
        owner_id=1, business_name="Demo",
    )
    assert "día" in response.lower() or "fecha" in response.lower()


@pytest.mark.asyncio
async def test_reschedule_invalid_date_shows_error(monkeypatch):
    _patch_ctx(monkeypatch)
    with patch("app.utils.date_parse.resolve_date_from_spanish_text", return_value=None):
        response = await execute_owner_route(
            1, owner_user_key("u1"),
            OwnerRouteDecision("flow_input", option="asdfgh", reason="flow_owner_reschedule_ask_date"),
            _ctx_with_item(status="P", state="owner_reschedule_ask_date"),
            owner_id=1, business_name="Demo",
        )
    assert "fecha" in response.lower() or "interpretar" in response.lower()


@pytest.mark.asyncio
async def test_reschedule_confirm_yes_calls_mutation(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_reschedule = AsyncMock(return_value=MutationResult(ok=True))
    monkeypatch.setattr("app.services.owner_command_router.owner_reschedule_appointment", mock_reschedule)

    slot = {"start_time": "10:00 AM", "start_datetime": "2026-05-10T10:00:00+00:00"}
    ctx = _ctx_with_item(status="P", state="owner_reschedule_confirm")
    ctx["pending_data"]["reschedule_chosen_slot"] = slot

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_reschedule_confirm"),
        ctx,
        owner_id=1, business_name="Demo",
    )
    mock_reschedule.assert_called_once()
    assert "reagendada" in response.lower()


@pytest.mark.asyncio
async def test_reschedule_not_reschedulable_shows_error(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_reschedule = AsyncMock(return_value=MutationResult(ok=False, error="not_reschedulable"))
    monkeypatch.setattr("app.services.owner_command_router.owner_reschedule_appointment", mock_reschedule)

    slot = {"start_time": "10:00 AM", "start_datetime": "2026-05-10T10:00:00+00:00"}
    ctx = _ctx_with_item(status="A", state="owner_reschedule_confirm")
    ctx["pending_data"]["reschedule_chosen_slot"] = slot

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_reschedule_confirm"),
        ctx,
        owner_id=1, business_name="Demo",
    )
    assert "no se puede reagendar" in response.lower()


# ── Block timeslot flow ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_block_option_6_asks_for_date(monkeypatch):
    _patch_ctx(monkeypatch)
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("menu_option", option="6", reason="option_6"),
        {"state": "idle"},
        owner_id=1, business_name="Demo",
    )
    assert "bloquear" in response.lower()
    assert "fecha" in response.lower()


@pytest.mark.asyncio
async def test_block_confirm_yes_calls_mutation(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_block = AsyncMock(return_value=MutationResult(ok=True))
    monkeypatch.setattr("app.services.owner_command_router.owner_block_timeslot", mock_block)

    ctx = {
        "state": "owner_block_confirm",
        "pending_data": {
            "block_start_dt": "2026-05-10T14:00:00+00:00",
            "block_end_dt": "2026-05-10T16:00:00+00:00",
        },
    }
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_block_confirm"),
        ctx,
        owner_id=1, business_name="Demo",
    )
    mock_block.assert_called_once()
    assert "bloqueado" in response.lower()


@pytest.mark.asyncio
async def test_block_conflict_shows_error(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_block = AsyncMock(return_value=MutationResult(ok=False, error="conflict:Juan, María"))
    monkeypatch.setattr("app.services.owner_command_router.owner_block_timeslot", mock_block)

    ctx = {
        "state": "owner_block_confirm",
        "pending_data": {
            "block_start_dt": "2026-05-10T14:00:00+00:00",
            "block_end_dt": "2026-05-10T16:00:00+00:00",
        },
    }
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_block_confirm"),
        ctx,
        owner_id=1, business_name="Demo",
    )
    assert "citas activas" in response.lower()
    assert "Juan" in response


@pytest.mark.asyncio
async def test_block_no_aborts_and_shows_menu(monkeypatch):
    _patch_ctx(monkeypatch)
    ctx = {
        "state": "owner_block_confirm",
        "pending_data": {
            "block_start_dt": "2026-05-10T14:00:00+00:00",
            "block_end_dt": "2026-05-10T16:00:00+00:00",
        },
    }
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="no", reason="flow_owner_block_confirm"),
        ctx,
        owner_id=1, business_name="Demo",
    )
    assert "cancelado" in response.lower() or "Panel rápido" in response


# ── Notifications ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notifications_option_5_calls_toggle(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_toggle = AsyncMock(return_value=True)
    monkeypatch.setattr("app.services.owner_command_router.db_service.toggle_business_notifications", mock_toggle)

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("menu_option", option="5", reason="option_5"),
        {"state": "idle"},
        owner_id=1, business_name="Demo",
    )
    mock_toggle.assert_called_once_with(1, 1)
    assert "activadas" in response.lower() or "notificaciones" in response.lower()


@pytest.mark.asyncio
async def test_notifications_disabled_shows_off_state(monkeypatch):
    _patch_ctx(monkeypatch)
    mock_toggle = AsyncMock(return_value=False)
    monkeypatch.setattr("app.services.owner_command_router.db_service.toggle_business_notifications", mock_toggle)

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("menu_option", option="5", reason="option_5"),
        {"state": "idle"},
        owner_id=1, business_name="Demo",
    )
    assert "desactivadas" in response.lower()


# ── owner_mutations unit tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_owner_cancel_not_found_returns_error(monkeypatch):
    from app.services.owner_mutations import owner_cancel_appointment
    monkeypatch.setattr("app.services.owner_mutations.db_service.get_appointment_for_owner", AsyncMock(return_value=None))
    result = await owner_cancel_appointment(99, 1)
    assert not result.ok
    assert result.error == "not_found"


@pytest.mark.asyncio
async def test_owner_cancel_already_cancelled_returns_error(monkeypatch):
    from app.services.owner_mutations import owner_cancel_appointment
    monkeypatch.setattr(
        "app.services.owner_mutations.db_service.get_appointment_for_owner",
        AsyncMock(return_value={"id": 1, "status": "A", "business_id": 1}),
    )
    result = await owner_cancel_appointment(1, 1)
    assert not result.ok
    assert result.error == "not_cancellable"


@pytest.mark.asyncio
async def test_owner_complete_already_cancelled_returns_error(monkeypatch):
    from app.services.owner_mutations import owner_complete_appointment
    monkeypatch.setattr(
        "app.services.owner_mutations.db_service.get_appointment_for_owner",
        AsyncMock(return_value={"id": 1, "status": "A", "business_id": 1}),
    )
    result = await owner_complete_appointment(1, 1)
    assert not result.ok
    assert result.error == "not_completable"


@pytest.mark.asyncio
async def test_owner_block_invalid_window_returns_error():
    from app.services.owner_mutations import owner_block_timeslot
    from datetime import datetime, timezone
    start = datetime(2026, 5, 10, 16, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc)
    result = await owner_block_timeslot(1, 1, start, end)
    assert not result.ok
    assert result.error == "invalid_window"


@pytest.mark.asyncio
async def test_owner_block_conflict_returns_error(monkeypatch):
    from app.services.owner_mutations import owner_block_timeslot
    from datetime import datetime, timezone
    monkeypatch.setattr(
        "app.services.owner_mutations.db_service.get_active_appointments_in_window",
        AsyncMock(return_value=[{"id": 5, "customer_name": "Pedro"}]),
    )
    start = datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 10, 16, 0, tzinfo=timezone.utc)
    result = await owner_block_timeslot(1, 1, start, end)
    assert not result.ok
    assert "conflict" in (result.error or "")
    assert "Pedro" in (result.error or "")


@pytest.mark.asyncio
async def test_owner_block_success(monkeypatch):
    from app.services.owner_mutations import owner_block_timeslot
    from datetime import datetime, timezone
    monkeypatch.setattr(
        "app.services.owner_mutations.db_service.get_active_appointments_in_window",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.owner_mutations.db_service.create_time_block",
        AsyncMock(return_value={"id": 10}),
    )
    start = datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 10, 16, 0, tzinfo=timezone.utc)
    result = await owner_block_timeslot(1, 1, start, end)
    assert result.ok


# ── Navigation: back from action states ───────────────────────────────────────

@pytest.mark.asyncio
async def test_back_from_cancel_confirm_returns_appointment_detail(monkeypatch):
    _patch_ctx(monkeypatch)
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("go_back", reason="back"),
        _ctx_with_item(status="P", state="owner_cancel_confirm"),
        owner_id=1, business_name="Demo",
    )
    assert "Cita #" in response


@pytest.mark.asyncio
async def test_back_from_block_date_returns_menu(monkeypatch):
    _patch_ctx(monkeypatch)
    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("go_back", reason="back"),
        {"state": "owner_block_ask_date", "pending_data": {}},
        owner_id=1, business_name="Demo",
    )
    assert "Panel rápido" in response


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_item(status: str = "P") -> dict:
    return {
        "appointment_id": 42,
        "local_time": "10:00 AM",
        "customer_name": "Juan",
        "customer_phone": "809-555-1234",
        "service_name": "Corte",
        "status": status,
        "status_label": {"P": "pendiente", "C": "confirmada", "A": "cancelada", "D": "completada"}.get(status, status),
        "price": 500.0,
    }


def _ctx_with_item(status: str = "P", state: str = "owner_appointment_detail") -> dict:
    item = _make_item(status)
    return {
        "state": state,
        "pending_data": {
            "selected_item": item,
            "owner_agenda": [item],
            "owner_agenda_kind": "today",
        },
    }


def _patch_ctx(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )


def _make_item_with_service(status: str = "P", service_id=5) -> dict:
    """Like _make_item but with service_id for reschedule tests."""
    return {
        "appointment_id": 42,
        "local_time": "10:00 AM",
        "customer_name": "Juan",
        "customer_phone": "829-000-0000",
        "service_name": "Corte",
        "service_id": service_id,
        "status": status,
        "status_label": "pendiente",
        "price": 300,
    }


def _ctx_with_service_item(status: str = "P", state: str = "owner_appointment_detail", service_id=5) -> dict:
    item = _make_item_with_service(status=status, service_id=service_id)
    return {
        "state": state,
        "pending_data": {
            "selected_item": item,
            "owner_agenda": [item],
            "owner_agenda_kind": "today",
        },
    }


# ── Edge case tests: reschedule and block ──────────────────────────────────────

@pytest.mark.asyncio
async def test_reschedule_service_id_none_returns_error(monkeypatch):
    """When selected_item has no service_id, _reschedule_fetch_slots must return an error
    mentioning 'servicio' and must NOT call get_availability."""
    _patch_ctx(monkeypatch)

    mock_get_availability = AsyncMock()
    monkeypatch.setattr("app.services.owner_command_router.db_service.get_availability", mock_get_availability)

    item_no_service = {
        "appointment_id": 42,
        "local_time": "10:00 AM",
        "customer_name": "Juan",
        "customer_phone": "829-000-0000",
        "service_name": "Corte",
        # service_id intentionally absent (will be None via .get())
        "status": "P",
        "status_label": "pendiente",
        "price": 300,
    }
    ctx = {
        "state": "owner_reschedule_ask_date",
        "pending_data": {
            "selected_item": item_no_service,
            "reschedule_date": "2026-05-10",
        },
    }

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="2026-05-10", reason="flow_owner_reschedule_ask_date"),
        ctx,
        owner_id=1, business_name="Demo",
    )

    mock_get_availability.assert_not_called()
    assert "servicio" in response.lower()


@pytest.mark.asyncio
async def test_reschedule_no_slots_does_not_persist_date(monkeypatch):
    """When get_availability returns no slots, reschedule_date must NOT appear in the
    pending_data passed to update_context, and the state should be owner_reschedule_ask_date."""
    captured_calls: list[dict] = []

    async def mock_update_context(business_id, user_key, payload):
        captured_calls.append(payload)

    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        mock_update_context,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_availability",
        AsyncMock(return_value={"available_slots": []}),
    )
    with patch("app.utils.date_parse.resolve_date_from_spanish_text", return_value="2026-05-10"):
        response = await execute_owner_route(
            1, owner_user_key("u1"),
            OwnerRouteDecision("flow_input", option="el 10 de mayo", reason="flow_owner_reschedule_ask_date"),
            _ctx_with_service_item(status="P", state="owner_reschedule_ask_date"),
            owner_id=1, business_name="Demo",
        )

    # Find the _set_state call that writes the reschedule flow state
    state_calls = [c for c in captured_calls if c.get("state") == "owner_reschedule_ask_date"]
    assert state_calls, "Expected at least one update_context call with state=owner_reschedule_ask_date"
    for call in state_calls:
        pending = call.get("pending_data", {})
        assert "reschedule_date" not in pending, (
            "reschedule_date should NOT be persisted when no slots are available"
        )
    assert "disponibilidad" in response.lower() or "otro día" in response.lower() or "no hay" in response.lower()


@pytest.mark.asyncio
async def test_reschedule_slots_found_persists_date(monkeypatch):
    """When get_availability returns slots, the state should be owner_reschedule_slots
    and both reschedule_date and reschedule_slots must be present in pending_data."""
    captured_calls: list[dict] = []

    async def mock_update_context(business_id, user_key, payload):
        captured_calls.append(payload)

    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        mock_update_context,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )
    slots = [
        {"start_time": "10:00 AM", "start_datetime": "2026-05-10T10:00:00+00:00"},
        {"start_time": "11:00 AM", "start_datetime": "2026-05-10T11:00:00+00:00"},
    ]
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_availability",
        AsyncMock(return_value={"available_slots": slots}),
    )
    with patch("app.utils.date_parse.resolve_date_from_spanish_text", return_value="2026-05-10"):
        response = await execute_owner_route(
            1, owner_user_key("u1"),
            OwnerRouteDecision("flow_input", option="el 10 de mayo", reason="flow_owner_reschedule_ask_date"),
            _ctx_with_service_item(status="P", state="owner_reschedule_ask_date"),
            owner_id=1, business_name="Demo",
        )

    slot_state_calls = [c for c in captured_calls if c.get("state") == "owner_reschedule_slots"]
    assert slot_state_calls, "Expected update_context call with state=owner_reschedule_slots"
    persisted = slot_state_calls[-1].get("pending_data", {})
    assert "reschedule_date" in persisted, "reschedule_date must be persisted when slots are available"
    assert "reschedule_slots" in persisted, "reschedule_slots must be persisted when slots are available"
    assert "10:00 AM" in response


@pytest.mark.asyncio
async def test_reschedule_slot_missing_start_datetime_returns_error(monkeypatch):
    """In owner_reschedule_confirm state, if the chosen slot lacks start_datetime,
    the response must contain an error message and NOT call owner_reschedule_appointment."""
    _patch_ctx(monkeypatch)
    mock_reschedule = AsyncMock(return_value=MutationResult(ok=True))
    monkeypatch.setattr("app.services.owner_command_router.owner_reschedule_appointment", mock_reschedule)

    # Slot without start_datetime
    slot_no_dt = {"start_time": "10:00 AM"}
    ctx = _ctx_with_service_item(status="P", state="owner_reschedule_confirm")
    ctx["pending_data"]["reschedule_chosen_slot"] = slot_no_dt

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_reschedule_confirm"),
        ctx,
        owner_id=1, business_name="Demo",
    )

    mock_reschedule.assert_not_called()
    # The error message should mention the problem and include the owner menu
    assert "Panel rápido" in response or "información completa" in response.lower() or "intentá de nuevo" in response.lower()


@pytest.mark.asyncio
async def test_reschedule_date_not_saved_on_exception(monkeypatch):
    """When get_availability raises an exception, the state should be set to idle
    (not a reschedule state), so the session is not left in a broken state."""
    captured_calls: list[dict] = []

    async def mock_update_context(business_id, user_key, payload):
        captured_calls.append(payload)

    monkeypatch.setattr(
        "app.services.owner_command_router.conversation_manager.update_context",
        mock_update_context,
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_business",
        AsyncMock(return_value={"timezone": "America/Santo_Domingo"}),
    )
    monkeypatch.setattr(
        "app.services.owner_command_router.db_service.get_availability",
        AsyncMock(side_effect=RuntimeError("DB timeout")),
    )
    with patch("app.utils.date_parse.resolve_date_from_spanish_text", return_value="2026-05-10"):
        response = await execute_owner_route(
            1, owner_user_key("u1"),
            OwnerRouteDecision("flow_input", option="el 10 de mayo", reason="flow_owner_reschedule_ask_date"),
            _ctx_with_service_item(status="P", state="owner_reschedule_ask_date"),
            owner_id=1, business_name="Demo",
        )

    # After an exception, the session should be set to idle
    final_state_calls = [c for c in captured_calls if "state" in c]
    # The last meaningful state update should be idle (from _set_owner_idle)
    idle_calls = [c for c in final_state_calls if c.get("state") == "idle"]
    assert idle_calls, "Expected at least one update_context call with state=idle after exception"
    assert "error" in response.lower() or "intentá de nuevo" in response.lower()


@pytest.mark.asyncio
async def test_block_past_date_rejected(monkeypatch):
    """Sending a past date to the owner_block_ask_date flow must return an error
    mentioning 'pasó' without advancing the state."""
    _patch_ctx(monkeypatch)

    from datetime import date, timedelta
    # Use 2 days ago to stay unambiguously in the past regardless of UTC vs local offset.
    yesterday = (date.today() - timedelta(days=2)).isoformat()

    with patch("app.utils.date_parse.resolve_date_from_spanish_text", return_value=yesterday):
        response = await execute_owner_route(
            1, owner_user_key("u1"),
            OwnerRouteDecision("flow_input", option="ayer", reason="flow_owner_block_ask_date"),
            {"state": "owner_block_ask_date", "pending_data": {}},
            owner_id=1, business_name="Demo",
        )

    assert "pasó" in response.lower()
    # Must not advance to owner_block_ask_start
    assert "¿Desde qué hora?" not in response


@pytest.mark.asyncio
async def test_reschedule_valid_slot_calls_mutation(monkeypatch):
    """Happy-path verification: with service_id=5 in the item, the mutation is called
    correctly and the response confirms the reschedule. Verifies the fix did not break
    the normal flow."""
    _patch_ctx(monkeypatch)
    mock_reschedule = AsyncMock(return_value=MutationResult(ok=True))
    monkeypatch.setattr("app.services.owner_command_router.owner_reschedule_appointment", mock_reschedule)

    slot = {"start_time": "10:00 AM", "start_datetime": "2026-05-10T10:00:00+00:00"}
    ctx = _ctx_with_service_item(status="P", state="owner_reschedule_confirm")
    ctx["pending_data"]["reschedule_chosen_slot"] = slot

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("flow_input", option="sí", reason="flow_owner_reschedule_confirm"),
        ctx,
        owner_id=1, business_name="Demo",
    )

    mock_reschedule.assert_called_once_with(42, 1, "2026-05-10T10:00:00+00:00")
    assert "reagendada" in response.lower()


@pytest.mark.asyncio
async def test_reschedule_back_from_slots_returns_to_detail(monkeypatch):
    """From owner_reschedule_slots, sending '9' (go_back) must return the appointment
    detail view, not the menu."""
    _patch_ctx(monkeypatch)
    ctx = _ctx_with_service_item(status="P", state="owner_reschedule_slots")
    ctx["pending_data"]["reschedule_date"] = "2026-05-10"
    ctx["pending_data"]["reschedule_slots"] = [
        {"start_time": "10:00 AM", "start_datetime": "2026-05-10T10:00:00+00:00"},
    ]

    response = await execute_owner_route(
        1, owner_user_key("u1"),
        OwnerRouteDecision("go_back", reason="back"),
        ctx,
        owner_id=1, business_name="Demo",
    )

    assert "Cita #" in response
