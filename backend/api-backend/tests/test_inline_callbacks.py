"""
Routing y dispatch de callbacks inline (guided_menu_router) + fix bug #2
(dígitos sueltos no se interpretan como opciones globales del menú).
"""
import pytest

from app.core.response_builder import BotReply
from app.services import guided_menu_router as router
from app.utils import telegram_ui


def ctx(state="idle", **extra):
    base = {
        "business_id": 1,
        "phone_number": "tg:1",
        "state": state,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
        "last_screen": "other",
    }
    base.update(extra)
    return base


def cb(ns, value, reason=None):
    return router.RouteDecision(
        "inline_callback",
        payload={"ns": ns, "value": value},
        reason=reason or f"callback_{ns}",
    )


def _noop_update(monkeypatch, captured=None):
    async def fake_update(_b, _k, payload):
        if captured is not None:
            captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)


# ── Routing: texto de callback → decisión inline_callback ────────────────────

@pytest.mark.parametrize(
    "text",
    [
        "service_1",
        "day_2026-08-29",
        "time_2026-08-29_09:00",
        "slots_page_2",
        "month_1",
        "week_1",
        "menu_agendar",
        "nav_back",
        "confirm_yes",
        "cancel_appt_11",
        "cancel_confirm_yes",
        "modify_appt_12",
        "resume_yes",
    ],
)
def test_callback_text_routes_to_inline_callback(text):
    decision = router.route_guided_message(text, ctx(state="awaiting_service"))

    assert decision.kind == "inline_callback"
    assert decision.uses_ai is False


# ── Bug #2: dígitos sueltos atados al contexto ────────────────────────────────

def test_digit_after_open_question_is_not_global_menu_option():
    # Contexto idle tras una pregunta abierta (pantalla distinta del menú)
    decision = router.route_guided_message("5", ctx())

    assert decision.kind != "menu_option"


def test_digit_after_main_menu_is_menu_option():
    decision = router.route_guided_message("5", ctx(last_screen="main_menu"))

    assert decision.kind == "menu_option"
    assert decision.option == "5"


def test_digit_in_active_flow_still_goes_to_flow():
    decision = router.route_guided_message("5", ctx(state="awaiting_slot_selection"))

    assert decision.kind == "active_flow"


# ── Navegación (nav_*) ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nav_menu_callback_clears_and_shows_menu_with_keyboard(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    reply = await router.execute_guided_route(1, "tg:1", cb("nav", "menu"), ctx(state="awaiting_service"))

    assert isinstance(reply, BotReply)
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
    assert any(u.get("state") == "idle" for u in captured["updates"])
    assert captured["updates"][-1]["last_screen"] == "main_menu"


@pytest.mark.asyncio
async def test_nav_back_callback_pops_stack_and_returns_footer(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    reply = await router.execute_guided_route(
        1, "tg:1", cb("nav", "back"), ctx(state="awaiting_service", state_stack=["awaiting_date"])
    )

    assert "Volvemos" in reply
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
    assert captured["updates"][-1]["state"] == "awaiting_date"


@pytest.mark.asyncio
async def test_nav_exit_callback_clears_to_idle(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    reply = await router.execute_guided_route(1, "tg:1", cb("nav", "exit"), ctx(state="awaiting_service"))

    assert "cerré esta consulta" in reply
    assert any(u.get("state") == "idle" for u in captured["updates"])


# ── Menú (menu_*) ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_menu_agendar_starts_booking_with_service_buttons_and_footer(monkeypatch):
    captured = {}

    async def fake_services(_bid):
        return [
            {"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30},
            {"id": 2, "name": "Cerquillos", "price": 8, "duration_minutes": 15},
        ]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(router.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)

    reply = await router.execute_guided_route(1, "tg:1", cb("menu", "agendar"), ctx())

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0] == [
        {"text": "Corte", "callback_data": "service_1"},
        {"text": "Cerquillos", "callback_data": "service_2"},
    ]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
    assert any(u.get("state") == "awaiting_service" for u in captured["updates"])


@pytest.mark.asyncio
async def test_menu_ver_citas_dispatches_check(monkeypatch):
    async def fake_check(_nlu, _context):
        return BotReply("No tienes citas próximas.", keyboard=[[{"text": "x", "callback_data": "nav_menu"}]])

    monkeypatch.setattr(router, "handle_check_appointment", fake_check)

    reply = await router.execute_guided_route(1, "tg:1", cb("menu", "ver_citas"), ctx())

    assert "No tienes citas" in reply


@pytest.mark.asyncio
async def test_menu_horarios_dispatches_business_info(monkeypatch):
    async def fake_info(_bid):
        return BotReply("📍 Barbería\nHorarios: ...", keyboard=telegram_ui.with_footer([]))

    monkeypatch.setattr(router, "handle_business_info", fake_info)

    reply = await router.execute_guided_route(1, "tg:1", cb("menu", "horarios"), ctx())

    assert "Barbería" in reply


# ── Servicios (service_*) ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_callback_sets_service_and_continues(monkeypatch):
    captured = {}

    async def fake_services(_bid):
        return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    async def fake_book(_nlu, context):
        captured["book"] = context
        return BotReply("continuamos")

    monkeypatch.setattr(router.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)
    monkeypatch.setattr(router, "handle_book_appointment", fake_book)

    await router.execute_guided_route(
        1,
        "tg:1",
        cb("service", "1"),
        ctx(state="awaiting_service", current_intent="book_appointment", pending_data={}),
    )

    assert captured["book"]["pending_data"]["service"] == "Corte"
    assert captured["book"]["pending_data"]["service_id"] == 1


@pytest.mark.asyncio
async def test_service_callback_from_idle_catalog_starts_booking(monkeypatch):
    captured = {}

    async def fake_services(_bid):
        return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    async def fake_book(_nlu, context):
        captured["book"] = context
        return BotReply("continuamos")

    monkeypatch.setattr(router.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)
    monkeypatch.setattr(router, "handle_book_appointment", fake_book)

    await router.execute_guided_route(1, "tg:1", cb("service", "1"), ctx(pending_data={}))

    assert captured["book"]["pending_data"]["service"] == "Corte"
    assert captured["book"]["pending_data"]["service_id"] == 1


# ── Días (day_*) ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_day_callback_sets_date_for_booking(monkeypatch):
    captured = {}

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    async def fake_book(_nlu, context):
        captured["book"] = context
        return BotReply("horarios")

    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)
    monkeypatch.setattr(router, "handle_book_appointment", fake_book)

    await router.execute_guided_route(
        1,
        "tg:1",
        cb("day", "2026-08-29"),
        ctx(
            state="booking_current_week",
            current_intent="book_appointment",
            pending_data={"service_id": 3},
        ),
    )

    assert captured["book"]["pending_data"]["date"] == "2026-08-29"


# ── Horarios (time_*) ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_time_callback_selects_exact_slot(monkeypatch):
    captured = {}

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    async def fake_book(_nlu, context):
        captured["book"] = context
        return BotReply("confirmación")

    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)
    monkeypatch.setattr(router, "handle_book_appointment", fake_book)

    pending = {
        "date": "2026-08-29",
        "service_id": 3,
        "available_slots": [
            {"start_time": "9:00 AM", "start_datetime": "2026-08-29T09:00:00+00:00"},
            {"start_time": "9:15 AM", "start_datetime": "2026-08-29T09:15:00+00:00"},
        ],
    }
    await router.execute_guided_route(
        1,
        "tg:1",
        cb("time", ("2026-08-29", "09:15")),
        ctx(
            state="awaiting_slot_selection",
            current_intent="book_appointment",
            pending_data=pending,
        ),
    )

    assert captured["book"]["pending_data"]["selected_slot"]["start_time"] == "9:15 AM"


# ── Paginación de la grilla (slots_page_*) ────────────────────────────────────

@pytest.mark.asyncio
async def test_slots_page_callback_renders_grid_and_updates_page(monkeypatch):
    captured = {}

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)

    slots = [
        {"start_time": "10:00 AM", "start_datetime": f"2026-08-28T{10 + i:02d}:00:00+00:00"}
        for i in range(13)
    ]
    pending = {"date": "2026-08-28", "available_slots": slots, "slot_page": 0}
    reply = await router.execute_guided_route(
        1,
        "tg:1",
        cb("slots_page", "1"),
        ctx(state="awaiting_slot_selection", pending_data=pending),
    )

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "time_2026-08-28_22:00"
    assert captured["update"]["pending_data"]["slot_page"] == 1
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]


# ── Confirmación de cita (confirm_*) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_yes_dispatches_confirmation_with_synthetic_si(monkeypatch):
    captured = {}

    async def fake_confirm(nlu, _context):
        captured["raw"] = nlu["_raw_user_text"]
        return BotReply("✅ ¡Tu cita está confirmada!")

    monkeypatch.setattr(router, "handle_booking_confirmation", fake_confirm)

    await router.execute_guided_route(
        1,
        "tg:1",
        cb("confirm", "yes"),
        ctx(state="awaiting_booking_confirmation", pending_data={"selected_slot": {}}),
    )

    assert captured["raw"] == "sí"


@pytest.mark.asyncio
async def test_confirm_no_dispatches_with_no(monkeypatch):
    captured = {}

    async def fake_confirm(nlu, _context):
        captured["raw"] = nlu["_raw_user_text"]
        return BotReply("cambiamos")

    monkeypatch.setattr(router, "handle_booking_confirmation", fake_confirm)

    await router.execute_guided_route(
        1,
        "tg:1",
        cb("confirm", "no"),
        ctx(state="awaiting_booking_confirmation", pending_data={"selected_slot": {}}),
    )

    assert captured["raw"] == "no"


# ── Cancelar (cancel_appt_* / cancel_confirm_*) ──────────────────────────────

@pytest.mark.asyncio
async def test_cancel_appt_callback_shows_confirm_screen(monkeypatch):
    captured = {}

    async def fake_get(_aid, _cid):
        return {
            "id": 11,
            "service_name": "Corte",
            "start_at": "2026-08-28T09:00:00+00:00",
            "status": "C",
            "service_id": 1,
        }

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(router.db_service, "get_customer_appointment", fake_get)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)

    reply = await router.execute_guided_route(
        1,
        "tg:1",
        cb("cancel_appt", "11"),
        ctx(state="awaiting_appointment_selection", current_intent="cancel_appointment"),
    )

    assert "¿Confirmás" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["cancel_confirm_yes", "cancel_confirm_no"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
    assert captured["update"]["state"] == "awaiting_cancel_confirmation"
    assert captured["update"]["pending_data"]["appointment_id"] == 11


@pytest.mark.asyncio
async def test_cancel_appt_callback_from_idle_check_screen_works(monkeypatch):
    captured = {}

    async def fake_get(_aid, _cid):
        return {"id": 11, "service_name": "Corte", "start_at": "2026-08-28T09:00:00+00:00", "status": "C", "service_id": 1}

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(router.db_service, "get_customer_appointment", fake_get)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)

    reply = await router.execute_guided_route(1, "tg:1", cb("cancel_appt", "11"), ctx())

    assert "¿Confirmás" in reply
    assert captured["updates"][-1]["state"] == "awaiting_cancel_confirmation"


@pytest.mark.asyncio
async def test_cancel_confirm_yes_cancels_appointment(monkeypatch):
    captured = {}

    async def fake_cancel(appointment_id, notes=None):
        captured["aid"] = appointment_id
        return True

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(router.db_service, "cancel_appointment", fake_cancel)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)

    reply = await router.execute_guided_route(
        1,
        "tg:1",
        cb("cancel_confirm", "yes"),
        ctx(state="awaiting_cancel_confirmation", pending_data={"appointment_id": 11}),
    )

    assert "cancelada exitosamente" in reply
    assert captured["aid"] == 11
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
    assert any(u.get("state") == "idle" for u in captured["updates"])


# ── Modificar (modify_appt_*) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_modify_appt_callback_asks_new_date_with_days(monkeypatch):
    captured = {}

    async def fake_get(_aid, _cid):
        return {
            "id": 12,
            "service_name": "Corte",
            "start_at": "2026-08-28T09:00:00+00:00",
            "status": "C",
            "service_id": 1,
        }

    async def fake_days(*_a, **_k):
        return [{"date": "2026-08-29", "label": "Vie 29"}]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(router.db_service, "get_customer_appointment", fake_get)
    monkeypatch.setattr(router.db_service, "get_available_days_in_range", fake_days)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)

    reply = await router.execute_guided_route(
        1,
        "tg:1",
        cb("modify_appt", "12"),
        ctx(state="awaiting_appointment_selection_modify", current_intent="modify_appointment"),
    )

    assert reply.keyboard[0][0]["callback_data"] == "day_2026-08-29"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
    assert captured["updates"][-1]["state"] == "awaiting_new_date"
    assert captured["updates"][-1]["pending_data"]["selected_appointment_id"] == 12


@pytest.mark.asyncio
async def test_modify_appt_callback_from_idle_check_screen_works(monkeypatch):
    captured = {}

    async def fake_get(_aid, _cid):
        return {"id": 12, "service_name": "Corte", "start_at": "2026-08-28T09:00:00+00:00", "status": "C", "service_id": 1}

    async def fake_days(*_a, **_k):
        return [{"date": "2026-08-29", "label": "Vie 29"}]

    async def fake_update(_b, _k, payload):
        captured.setdefault("updates", []).append(payload)

    monkeypatch.setattr(router.db_service, "get_customer_appointment", fake_get)
    monkeypatch.setattr(router.db_service, "get_available_days_in_range", fake_days)
    monkeypatch.setattr(router.conversation_manager, "update_context", fake_update)

    reply = await router.execute_guided_route(1, "tg:1", cb("modify_appt", "12"), ctx())

    assert reply.keyboard[0][0]["callback_data"] == "day_2026-08-29"
    assert captured["updates"][-1]["state"] == "awaiting_new_date"


# ── Sesión vencida (resume_*) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resume_yes_restores_pending_data(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    reply = await router.execute_guided_route(
        1,
        "tg:1",
        cb("resume", "yes"),
        ctx(
            state="awaiting_session_resume",
            resume_data={"date": "2026-08-29"},
            resume_intent="book_appointment",
            resume_state="awaiting_date",
        ),
    )

    assert captured["updates"][-1]["state"] == "awaiting_date"
    assert captured["updates"][-1]["current_intent"] == "book_appointment"
    assert captured["updates"][-1]["pending_data"] == {"date": "2026-08-29"}
    assert reply.keyboard == telegram_ui.with_footer([])


# ── Callback huérfano ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stale_callback_returns_not_valid_and_menu(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    reply = await router.execute_guided_route(1, "tg:1", cb("confirm", "yes"), ctx())

    assert "ya no está vigente" in reply
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
    assert any(u.get("state") == "idle" for u in captured["updates"])


# ── Token de pantalla (callbacks firmados con |token) ─────────────────────────

@pytest.mark.asyncio
async def test_callback_with_old_token_is_blocked(monkeypatch):
    captured = {}
    _noop_update(monkeypatch, captured)

    decision = router.RouteDecision(
        "inline_callback",
        payload={"ns": "nav", "value": "menu", "token": "aaaa"},
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
