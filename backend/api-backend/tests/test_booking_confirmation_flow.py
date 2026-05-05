import asyncio

from app.handlers import booking_handler


def test_slot_selection_accepts_option_phrase(monkeypatch):
    async def _run():
        async def fake_get_services(_business_id):
            return [
                {"name": "Corte", "price": 10, "duration_minutes": 30},
                {"name": "Cerquillos", "price": 8, "duration_minutes": 15},
            ]

        captured = {"pending": None}

        async def fake_update_context(_bid, _phone, payload):
            captured["pending"] = payload["pending_data"]
            return None

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update_context)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "date": "2026-04-14",
                "available_slots": [
                    {"start_time": "9:00 AM", "start_datetime": "2026-04-14T09:00:00", "end_datetime": "2026-04-14T09:15:00"},
                    {"start_time": "9:15 AM", "start_datetime": "2026-04-14T09:15:00", "end_datetime": "2026-04-14T09:30:00"},
                    {"start_time": "9:30 AM", "start_datetime": "2026-04-14T09:30:00", "end_datetime": "2026-04-14T09:45:00"},
                    {"start_time": "9:45 AM", "start_datetime": "2026-04-14T09:45:00", "end_datetime": "2026-04-14T10:00:00"},
                ],
            },
        }
        nlu = {"_raw_user_text": "la opcion 4 me parece bien", "entities": {}}
        resp = await booking_handler.handle_slot_selection(nlu, context)

        assert "guardé tu horario" in resp.lower()
        assert "9:45 am" in resp.lower()
        assert captured["pending"]["selected_slot"]["start_time"] == "9:45 AM"

    asyncio.run(_run())


def test_service_persisted_when_date_asked_after_service_name(monkeypatch):
    """Evita perder el servicio elegido antes de la fecha (flujo fecha→slot→servicio)."""

    async def _run():
        captured = {}

        async def fake_get_services(_bid):
            return [
                {"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30},
                {"id": 2, "name": "Cerquillos", "price": 8, "duration_minutes": 15},
            ]

        async def fake_get_availability(**_kwargs):
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-04-17T10:00:00",
                        "end_datetime": "2026-04-17T10:30:00",
                    },
                ]
            }

        async def fake_update_context(_bid, _phone, payload):
            captured["last"] = payload
            return None

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update_context)

        base_ctx = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {},
        }

        nlu1 = {"_raw_user_text": "Corte", "entities": {}}
        r1 = await booking_handler.handle_book_appointment(nlu1, base_ctx)
        assert "esta semana" in r1.lower()
        assert captured["last"]["pending_data"].get("service") == "Corte"
        assert captured["last"]["pending_data"].get("service_id") == 1

        ctx2 = {**base_ctx, "pending_data": dict(captured["last"]["pending_data"])}
        nlu2 = {"_raw_user_text": "viernes", "entities": {"date": "2026-04-17"}}
        r2 = await booking_handler.handle_book_appointment(nlu2, ctx2)
        assert "horario" in r2.lower()
        assert captured["last"]["pending_data"].get("service") == "Corte"
        assert captured["last"]["pending_data"].get("available_slots")

    asyncio.run(_run())


def test_booking_confirmation_requires_yes_or_no():
    async def _run():
        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service_id": 3,
                "service": "Corte",
                "date": "2026-04-10",
                "selected_slot": {
                    "start_time": "10:00 AM",
                    "start_datetime": "2026-04-10T10:00:00",
                    "end_datetime": "2026-04-10T10:30:00",
                },
                "available_slots": [],
            },
        }
        nlu = {"_raw_user_text": "tal vez"}
        resp = await booking_handler.handle_booking_confirmation(nlu, context)
        assert "respondeme" in resp.lower() or "respondé" in resp.lower()

    asyncio.run(_run())


def test_booking_confirmation_yes_creates_appointment(monkeypatch):
    async def _run():
        called = {"created": False}

        async def fake_get_availability(**kwargs):
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-04-10T10:00:00",
                        "end_datetime": "2026-04-10T10:30:00",
                    }
                ]
            }

        async def fake_create_appointment(data):
            called["created"] = True
            return {"id": 123}

        async def fake_clear(*_args, **_kwargs):
            return None

        async def fake_get_business(_business_id):
            return {"name": "Barbería", "address": "Calle 1"}

        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.db_service, "create_appointment", fake_create_appointment)
        monkeypatch.setattr(booking_handler.db_service, "get_business", fake_get_business)
        monkeypatch.setattr(booking_handler.conversation_manager, "clear_pending_data", fake_clear)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_clear)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service_id": 3,
                "service": "Corte",
                "date": "2026-04-10",
                "selected_slot": {
                    "start_time": "10:00 AM",
                    "start_datetime": "2026-04-10T10:00:00",
                    "end_datetime": "2026-04-10T10:30:00",
                },
                "available_slots": [],
            },
        }
        nlu = {"_raw_user_text": "sí, confirmar"}
        resp = await booking_handler.handle_booking_confirmation(nlu, context)
        assert called["created"] is True
        assert "confirmada" in resp.lower()

    asyncio.run(_run())


def test_booking_confirmation_revalidates_slot_before_create(monkeypatch):
    async def _run():
        called = {"created": False, "updated": None}

        async def fake_get_availability(**_kwargs):
            return {"available_slots": []}

        async def fake_create_appointment(_data):
            called["created"] = True
            return {"id": 123}

        async def fake_update_context(_bid, _phone, payload):
            called["updated"] = payload
            return None

        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.db_service, "create_appointment", fake_create_appointment)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update_context)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service_id": 3,
                "service": "Corte",
                "date": "2026-04-10",
                "selected_slot": {
                    "start_time": "10:00 AM",
                    "start_datetime": "2026-04-10T10:00:00",
                    "end_datetime": "2026-04-10T10:30:00",
                },
                "available_slots": [],
            },
        }

        resp = await booking_handler.handle_booking_confirmation(
            {"_raw_user_text": "sí"},
            context,
        )

        assert called["created"] is False
        assert called["updated"]["state"] == "awaiting_slot_selection"
        assert "ya no está disponible" in resp.lower()

    asyncio.run(_run())


def test_booking_service_id_persisted_in_slot_selection_pending_data(monkeypatch):
    """spec 004 T004 — bug fix: service_id debe persistir en pending_data al mostrar slots sin hora."""

    async def _run():
        captured = {"pending": None}

        async def fake_get_services(_bid):
            return [{"id": 42, "name": "Corte", "price": 10, "duration_minutes": 30}]

        async def fake_get_availability(**_kwargs):
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-06-10T10:00:00",
                        "end_datetime": "2026-06-10T10:30:00",
                    },
                ]
            }

        async def fake_update_context(_bid, _phone, payload):
            captured["pending"] = payload.get("pending_data", {})
            return None

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update_context)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {"date": "2026-06-10", "service": "Corte"},
            "state": "awaiting_date",
        }
        nlu = {"_raw_user_text": "el 10 de junio", "entities": {}}
        await booking_handler.handle_book_appointment(nlu, context)

        assert captured["pending"] is not None, "update_context no fue llamado"
        assert captured["pending"].get("service_id") == 42, (
            f"service_id debería ser 42 pero es {captured['pending'].get('service_id')}"
        )
        assert "available_slots" in captured["pending"]

    import asyncio
    asyncio.run(_run())


def test_direct_shortcut_enters_guided_flow_without_creating(monkeypatch):
    async def _run():
        captured = {"context": None, "created": False}

        async def fake_get_services(_business_id):
            return [{"id": 3, "name": "Corte", "price": 500, "duration_minutes": 30}]

        async def fake_get_availability(**_kwargs):
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-04-10T10:00:00",
                        "end_datetime": "2026-04-10T10:30:00",
                    }
                ]
            }

        async def fake_update_context(_bid, _phone, payload):
            captured["context"] = payload
            return None

        async def fake_create_appointment(_data):
            captured["created"] = True
            return {"id": 123}

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.db_service, "create_appointment", fake_create_appointment)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update_context)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {},
        }
        nlu = {
            "_raw_user_text": "quiero cita mañana a las 10",
            "entities": {"service": "Corte", "date": "2026-04-10", "time": "10:00"},
        }

        resp = await booking_handler.handle_book_appointment(nlu, context)

        assert captured["created"] is False
        assert captured["context"]["state"] in {
            "awaiting_slot_selection",
            "awaiting_booking_confirmation",
        }
        assert "confirmada" not in resp.lower()

    asyncio.run(_run())


# --- Tests spec 004 T013: session resume ---

def test_expired_flow_with_pending_asks_resume(monkeypatch):
    """expired_flow with non-empty pending_data → asks to resume, sets awaiting_session_resume."""
    import asyncio
    from app.services import guided_menu_router as gmr

    async def _run():
        captured = {}

        async def fake_update(_bid, _key, payload):
            captured.update(payload)

        monkeypatch.setattr(gmr.conversation_manager, "update_context", fake_update)

        from app.services.guided_menu_router import RouteDecision, execute_guided_route

        decision = RouteDecision("expired_flow")
        context = {
            "state": "awaiting_slot_selection",
            "current_intent": "book_appointment",
            "pending_data": {"service": "Corte", "date": "2026-06-10"},
            "customer_name": "Ana",
        }
        resp = await execute_guided_route(1, "tg:1", decision, context)

        assert "continuamos" in resp.lower() or "medias" in resp.lower()
        assert captured.get("state") == "awaiting_session_resume"
        assert captured.get("resume_data") == {"service": "Corte", "date": "2026-06-10"}
        assert captured.get("resume_intent") == "book_appointment"

    asyncio.run(_run())


def test_expired_flow_without_pending_clears_to_idle(monkeypatch):
    """expired_flow with empty pending_data → clears immediately and shows menu."""
    import asyncio
    from app.services import guided_menu_router as gmr

    async def _run():
        captured = {}

        async def fake_update(_bid, _key, payload):
            captured.update(payload)

        monkeypatch.setattr(gmr.conversation_manager, "update_context", fake_update)

        from app.services.guided_menu_router import RouteDecision, execute_guided_route

        decision = RouteDecision("expired_flow")
        context = {
            "state": "awaiting_service",
            "current_intent": "book_appointment",
            "pending_data": {},
            "customer_name": "",
        }
        resp = await execute_guided_route(1, "tg:1", decision, context)

        assert "inactividad" in resp.lower()
        assert captured.get("state") == "idle"

    asyncio.run(_run())


def test_session_resume_yes_restores_context(monkeypatch):
    """awaiting_session_resume + 'sí' → restores pending_data and previous state."""
    import asyncio
    from app.core import orchestrator as orch

    async def _run():
        captured = {}

        async def fake_save_msg(*_args, **_kwargs):
            return None

        async def fake_update(_bid, _key, payload):
            captured.update(payload)

        async def fake_get_context(_bid, _key):
            return {
                "state": "awaiting_session_resume",
                "current_intent": None,
                "customer_id": 7,
                "customer_name": "Ana",
                "pending_data": {},
                "resume_data": {"service": "Corte", "date": "2026-06-10"},
                "resume_intent": "book_appointment",
                "resume_state": "awaiting_date",
                "recent_messages": [],
                "state_stack": [],
            }

        monkeypatch.setattr(orch.conversation_manager, "save_message", fake_save_msg)
        monkeypatch.setattr(orch.conversation_manager, "update_context", fake_update)
        monkeypatch.setattr(orch.conversation_manager, "get_context", fake_get_context)

        # ensure_coherent_context pass-through
        from app.core import state_machine
        async def ensure_coherent_context(_b, _k, ctx):
            return ctx
        monkeypatch.setattr(state_machine, "ensure_coherent_context", ensure_coherent_context)

        resp = await orch.run_conversation_turn(1, "tg:1", "sí")

        assert "continuamos" in resp.lower()
        assert captured.get("state") == "awaiting_date"
        assert captured.get("current_intent") == "book_appointment"
        assert captured.get("pending_data") == {"service": "Corte", "date": "2026-06-10"}
        assert captured.get("resume_data") is None

    asyncio.run(_run())


# --- Tests spec 004 T017: state_stack back navigation ---

def test_back_from_slot_selection_returns_awaiting_date(monkeypatch):
    """go_back with non-empty stack → restores previous state, stack shrinks."""
    import asyncio
    from app.services import guided_menu_router as gmr

    async def _run():
        captured = {}

        async def fake_update(_bid, _key, payload):
            captured.update(payload)

        monkeypatch.setattr(gmr.conversation_manager, "update_context", fake_update)

        from app.services.guided_menu_router import RouteDecision, execute_guided_route

        decision = RouteDecision("go_back")
        context = {
            "state": "awaiting_slot_selection",
            "current_intent": "book_appointment",
            "pending_data": {"service": "Corte", "date": "2026-06-10"},
            "state_stack": ["awaiting_date"],
            "customer_name": "Ana",
        }
        resp = await execute_guided_route(1, "tg:1", decision, context)

        assert "volvemos" in resp.lower() or "anterior" in resp.lower()
        assert captured.get("state") == "awaiting_date"
        assert captured.get("state_stack") == []

    asyncio.run(_run())


def test_back_from_awaiting_date_returns_idle_when_stack_empty(monkeypatch):
    """go_back with empty stack → clears to idle and shows menu."""
    import asyncio
    from app.services import guided_menu_router as gmr

    async def _run():
        captured = {}

        async def fake_update(_bid, _key, payload):
            captured.update(payload)

        monkeypatch.setattr(gmr.conversation_manager, "update_context", fake_update)

        from app.services.guided_menu_router import RouteDecision, execute_guided_route

        decision = RouteDecision("go_back")
        context = {
            "state": "awaiting_date",
            "current_intent": "book_appointment",
            "pending_data": {"service": "Corte"},
            "state_stack": [],
            "customer_name": "Ana",
        }
        resp = await execute_guided_route(1, "tg:1", decision, context)

        assert "1)" in resp or "agendar" in resp.lower()
        assert captured.get("state") == "idle"

    asyncio.run(_run())


def test_back_preserves_pending_data(monkeypatch):
    """Going back does not clear pending_data."""
    import asyncio
    from app.services import guided_menu_router as gmr

    async def _run():
        captured = {}

        async def fake_update(_bid, _key, payload):
            captured.update(payload)

        monkeypatch.setattr(gmr.conversation_manager, "update_context", fake_update)

        from app.services.guided_menu_router import RouteDecision, execute_guided_route

        decision = RouteDecision("go_back")
        context = {
            "state": "awaiting_slot_selection",
            "current_intent": "book_appointment",
            "pending_data": {"service": "Cerquillos", "date": "2026-07-01"},
            "state_stack": ["awaiting_service", "awaiting_date"],
            "customer_name": "",
        }
        await execute_guided_route(1, "tg:1", decision, context)

        # pending_data should not have been included in the update (i.e., not cleared)
        assert "pending_data" not in captured

    asyncio.run(_run())


# --- Tests spec 004 T020: attempt counter ---

def test_three_invalid_attempts_redirects_to_menu(monkeypatch):
    """3 failed inputs in same state → orchestrator clears and returns menu."""
    import asyncio
    from app.core import orchestrator as orch

    async def _run():
        cleared = {"done": False}
        saved_responses = []

        async def fake_save_msg(_bid, _key, role, content, *_a, **_kw):
            if role == "assistant":
                saved_responses.append(content)

        call_count = {"n": 0}

        async def fake_get_context(_bid, _key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: initial context
                return {
                    "state": "awaiting_date",
                    "current_intent": "book_appointment",
                    "customer_id": 7,
                    "customer_name": "Ana",
                    "pending_data": {"service": "Corte"},
                    "recent_messages": [],
                    "state_stack": [],
                    "attempts": {"awaiting_date": 2},  # already 2 attempts
                }
            # Second call (post-handler check): state unchanged
            return {
                "state": "awaiting_date",
                "current_intent": "book_appointment",
                "customer_name": "Ana",
                "pending_data": {"service": "Corte"},
                "state_stack": [],
                "attempts": {"awaiting_date": 2},
            }

        async def fake_update(_bid, _key, payload):
            if payload.get("state") == "idle":
                cleared["done"] = True

        async def fake_handle_book(*_args, **_kwargs):
            return "¿Qué fecha querés?"

        _synthetic_nlu = {
            "intent": "book_appointment",
            "entities": {},
            "confidence": 1.0,
            "missing": [],
            "raw_understanding": "test",
            "response_text": "",
        }

        from app.core import state_machine
        async def ensure_coherent_context(_b, _k, ctx):
            return ctx
        monkeypatch.setattr(state_machine, "ensure_coherent_context", ensure_coherent_context)
        monkeypatch.setattr(orch.conversation_manager, "save_message", fake_save_msg)
        monkeypatch.setattr(orch.conversation_manager, "get_context", fake_get_context)
        monkeypatch.setattr(orch.conversation_manager, "update_context", fake_update)
        async def fake_build_ctx(*a, **kw):
            return ""

        monkeypatch.setattr(orch, "handle_book_appointment", fake_handle_book)
        monkeypatch.setattr(orch, "build_customer_context_for_nlu", fake_build_ctx)
        monkeypatch.setattr(orch, "try_booking_flow_synthetic_nlu", lambda **kw: _synthetic_nlu)

        resp = await orch.run_conversation_turn(1, "tg:1", "blablabla")

        assert cleared["done"] is True
        assert "menú" in resp.lower() or "menu" in resp.lower() or "intentos" in resp.lower()

    asyncio.run(_run())


def test_attempt_counter_resets_on_state_advance(monkeypatch):
    """When state advances, attempt counter for old state is cleared."""
    import asyncio
    from app.core import orchestrator as orch

    async def _run():
        attempts_saved = {}

        async def fake_save_msg(*_a, **_kw):
            return None

        call_count = {"n": 0}

        async def fake_get_context(_bid, _key):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {
                    "state": "awaiting_date",
                    "current_intent": "book_appointment",
                    "customer_id": 7,
                    "customer_name": "Ana",
                    "pending_data": {"service": "Corte"},
                    "recent_messages": [],
                    "state_stack": [],
                    "attempts": {"awaiting_date": 1},
                }
            # Second call: state advanced to awaiting_slot_selection
            return {
                "state": "awaiting_slot_selection",
                "current_intent": "book_appointment",
                "customer_name": "Ana",
                "pending_data": {"service": "Corte", "date": "2026-06-10"},
                "state_stack": ["awaiting_date"],
                "attempts": {"awaiting_date": 1},
            }

        async def fake_update(_bid, _key, payload):
            if "attempts" in payload:
                attempts_saved.update(payload["attempts"])

        async def fake_handle_book(*_args, **_kwargs):
            return "¿Qué horario preferís?"

        _synthetic_nlu = {
            "intent": "book_appointment",
            "entities": {"date": "2026-06-10"},
            "confidence": 1.0,
            "missing": [],
            "raw_understanding": "test",
            "response_text": "",
        }

        from app.core import state_machine
        async def ensure_coherent_context(_b, _k, ctx):
            return ctx
        monkeypatch.setattr(state_machine, "ensure_coherent_context", ensure_coherent_context)
        monkeypatch.setattr(orch.conversation_manager, "save_message", fake_save_msg)
        monkeypatch.setattr(orch.conversation_manager, "get_context", fake_get_context)
        monkeypatch.setattr(orch.conversation_manager, "update_context", fake_update)
        async def fake_build_ctx2(*a, **kw):
            return ""

        monkeypatch.setattr(orch, "handle_book_appointment", fake_handle_book)
        monkeypatch.setattr(orch, "build_customer_context_for_nlu", fake_build_ctx2)
        monkeypatch.setattr(orch, "try_booking_flow_synthetic_nlu", lambda **kw: _synthetic_nlu)

        await orch.run_conversation_turn(1, "tg:1", "el 10 de junio")

        # awaiting_date should have been removed from attempts
        assert "awaiting_date" not in attempts_saved

    asyncio.run(_run())


# --- Tests spec 004 T024: próximos días sugeridos ---

def test_no_slots_shows_next_available_days(monkeypatch):
    """When requested date has no slots, alternatives are shown and saved in suggested_days."""
    import asyncio
    from app.handlers import booking_handler

    async def _run():
        captured = {}

        async def fake_get_services(_bid):
            return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

        async def fake_get_availability(**_kwargs):
            return {"available_slots": []}

        async def fake_get_next_days(**_kwargs):
            return [
                {"date": "2026-06-11"},
                {"date": "2026-06-12"},
                {"date": "2026-06-13"},
            ]

        async def fake_update(_bid, _phone, payload):
            captured.update(payload)

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.db_service, "get_next_available_days", fake_get_next_days)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {"service": "Corte"},
        }
        nlu = {"_raw_user_text": "el lunes", "entities": {"date": "2026-06-10"}}
        resp = await booking_handler.handle_book_appointment(nlu, context)

        assert "disponibles" in resp.lower() or "1." in resp
        assert captured.get("pending_data", {}).get("suggested_days") is not None
        assert len(captured["pending_data"]["suggested_days"]) == 3

    asyncio.run(_run())


def test_no_slots_no_alternatives_shows_generic_message(monkeypatch):
    """When no slots and no alternatives, generic message shown, suggested_days not set."""
    import asyncio
    from app.handlers import booking_handler

    async def _run():
        captured = {}

        async def fake_get_services(_bid):
            return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

        async def fake_get_availability(**_kwargs):
            return {"available_slots": []}

        async def fake_get_next_days(**_kwargs):
            return []

        async def fake_update(_bid, _phone, payload):
            captured.update(payload)

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.db_service, "get_next_available_days", fake_get_next_days)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {"service": "Corte"},
        }
        nlu = {"_raw_user_text": "el lunes", "entities": {"date": "2026-06-10"}}
        resp = await booking_handler.handle_book_appointment(nlu, context)

        assert "otro día" in resp.lower() or "disponibles" not in resp.lower() or "1." not in resp
        assert "suggested_days" not in captured.get("pending_data", {})

    asyncio.run(_run())


def test_user_selects_suggested_day(monkeypatch):
    """User replies '2' → second suggested day is used as the date."""
    import asyncio
    from app.handlers import booking_handler

    async def _run():
        captured = {}

        async def fake_get_services(_bid):
            return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

        async def fake_get_availability(**_kwargs):
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-06-12T10:00:00",
                        "end_datetime": "2026-06-12T10:30:00",
                    }
                ]
            }

        async def fake_update(_bid, _phone, payload):
            captured.update(payload)

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service": "Corte",
                "suggested_days": [
                    {"date": "2026-06-11"},
                    {"date": "2026-06-12"},
                    {"date": "2026-06-13"},
                ],
            },
        }
        nlu = {"_raw_user_text": "2", "entities": {}}
        resp = await booking_handler.handle_book_appointment(nlu, context)

        assert "horario" in resp.lower() or "10:00" in resp.lower()
        assert "suggested_days" not in captured.get("pending_data", {})
        assert captured.get("pending_data", {}).get("available_slots") is not None

    asyncio.run(_run())


# --- Tests spec 004 T030: slot pagination ---

def test_slot_pagination_shows_next_button(monkeypatch):
    """When slots > page_size, _slots_short_list shows '8) Siguiente →'."""
    from app.handlers.booking_handler import _paginate_slots, _slots_short_list, _SLOTS_PAGE_SIZE

    slots = [
        {"start_time": f"{9+i}:00 AM", "start_datetime": f"2026-06-10T{9+i:02d}:00:00", "end_datetime": f"2026-06-10T{9+i:02d}:30:00"}
        for i in range(_SLOTS_PAGE_SIZE + 2)
    ]
    page_info = _paginate_slots(slots, page=0)
    rendered = _slots_short_list(page_info)

    assert "8)" in rendered and "iguiente" in rendered
    assert "7)" not in rendered  # no prev on first page


def test_slot_page_navigation_forward(monkeypatch):
    """Raw input '8' with has_next → slot_page incremented, new page shown."""
    import asyncio
    from app.handlers import booking_handler
    from app.handlers.booking_handler import _SLOTS_PAGE_SIZE

    async def _run():
        captured = {}

        async def fake_update(_bid, _phone, payload):
            captured.update(payload)

        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        slots = [
            {
                "start_time": f"{9+i}:00 AM",
                "start_datetime": f"2026-06-10T{9+i:02d}:00:00",
                "end_datetime": f"2026-06-10T{9+i:02d}:30:00",
            }
            for i in range(_SLOTS_PAGE_SIZE + 2)
        ]
        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service": "Corte",
                "service_id": 1,
                "date": "2026-06-10",
                "available_slots": slots,
                "slot_page": 0,
            },
        }
        nlu = {"_raw_user_text": "8", "entities": {}}
        resp = await booking_handler.handle_slot_selection(nlu, context)

        assert captured.get("pending_data", {}).get("slot_page") == 1
        assert "página 2" in resp.lower() or "2" in resp

    asyncio.run(_run())


def test_slot_page_navigation_backward(monkeypatch):
    """Raw input '7' on page 1 with has_prev → slot_page decremented."""
    import asyncio
    from app.handlers import booking_handler
    from app.handlers.booking_handler import _SLOTS_PAGE_SIZE

    async def _run():
        captured = {}

        async def fake_update(_bid, _phone, payload):
            captured.update(payload)

        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        slots = [
            {
                "start_time": f"{9+i}:00 AM",
                "start_datetime": f"2026-06-10T{9+i:02d}:00:00",
                "end_datetime": f"2026-06-10T{9+i:02d}:30:00",
            }
            for i in range(_SLOTS_PAGE_SIZE + 2)
        ]
        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service": "Corte",
                "service_id": 1,
                "date": "2026-06-10",
                "available_slots": slots,
                "slot_page": 1,
            },
        }
        nlu = {"_raw_user_text": "7", "entities": {}}
        resp = await booking_handler.handle_slot_selection(nlu, context)

        assert captured.get("pending_data", {}).get("slot_page") == 0
        assert "página 1" in resp.lower() or "1" in resp

    asyncio.run(_run())


def test_slot_selection_correct_on_page_2(monkeypatch):
    """Selecting slot '1' on page 2 resolves to the first slot of that page."""
    import asyncio
    from app.handlers import booking_handler
    from app.handlers.booking_handler import _SLOTS_PAGE_SIZE

    async def _run():
        captured = {}

        async def fake_update(_bid, _phone, payload):
            captured["pending"] = payload.get("pending_data", {})

        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        slots = [
            {
                "start_time": f"{9+i}:00 AM",
                "start_datetime": f"2026-06-10T{9+i:02d}:00:00",
                "end_datetime": f"2026-06-10T{9+i:02d}:30:00",
            }
            for i in range(_SLOTS_PAGE_SIZE + 2)
        ]
        first_slot_page2 = slots[_SLOTS_PAGE_SIZE]  # first slot of page 1 (0-indexed)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service": "Corte",
                "service_id": 1,
                "date": "2026-06-10",
                "available_slots": slots,
                "slot_page": 1,
            },
        }
        nlu = {"_raw_user_text": "1", "entities": {}}
        resp = await booking_handler.handle_slot_selection(nlu, context)

        selected = captured.get("pending", {}).get("selected_slot")
        assert selected is not None
        assert selected["start_time"] == first_slot_page2["start_time"]

    asyncio.run(_run())


# --- Tests spec 004 T035: double booking conflict ---

def test_double_booking_conflict_handled_gracefully(monkeypatch):
    """When create_appointment returns slot_conflict, handler shows fresh alternatives."""
    import asyncio
    from app.handlers import booking_handler

    async def _run():
        captured = {}

        async def fake_get_availability(**_kwargs):
            # revalidation passes (slot still appears free)
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-06-10T10:00:00",
                        "end_datetime": "2026-06-10T10:30:00",
                    }
                ]
            }

        async def fake_create_appointment(_data):
            return {"error": "slot_conflict"}

        async def fake_update(_bid, _phone, payload):
            captured.update(payload)

        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.db_service, "create_appointment", fake_create_appointment)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "pending_data": {
                "service_id": 1,
                "service": "Corte",
                "date": "2026-06-10",
                "selected_slot": {
                    "start_time": "10:00 AM",
                    "start_datetime": "2026-06-10T10:00:00",
                    "end_datetime": "2026-06-10T10:30:00",
                },
                "available_slots": [],
            },
        }
        nlu = {"_raw_user_text": "sí"}
        resp = await booking_handler.handle_booking_confirmation(nlu, context)

        assert "reservado" in resp.lower() or "conflicto" in resp.lower() or "otra persona" in resp.lower()
        assert captured.get("state") == "awaiting_slot_selection"
        assert "created" not in str(resp).lower() or "confirmada" not in resp.lower()

    asyncio.run(_run())
