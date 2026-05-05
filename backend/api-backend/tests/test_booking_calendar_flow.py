import asyncio
from datetime import date

from app.core import orchestrator as orch
from app.handlers import booking_calendar_handler as calendar_handler
from app.handlers import booking_handler
from app.services import db_service


def test_get_available_days_in_range_filters_empty_days(monkeypatch):
    async def _run():
        async def fake_get_availability(**kwargs):
            if kwargs["date"] == "2026-06-02":
                return {"available_slots": [{"start_time": "10:00 AM"}]}
            return {"available_slots": []}

        monkeypatch.setattr(db_service, "get_availability", fake_get_availability)

        days = await db_service.get_available_days_in_range(
            business_id=1,
            service_id=3,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
        )

        assert days == [{"date": "2026-06-02", "slot_count": 1, "label": "martes 2"}]

    asyncio.run(_run())


def test_current_week_shows_available_days(monkeypatch):
    async def _run():
        captured = {}

        async def fake_days(**_kwargs):
            return [
                {"date": "2026-06-03", "slot_count": 2, "label": "miércoles 3"},
                {"date": "2026-06-05", "slot_count": 1, "label": "viernes 5"},
            ]

        async def fake_update(_bid, _user, payload):
            captured.update(payload)

        monkeypatch.setattr(calendar_handler, "_today", lambda: date(2026, 6, 1))
        monkeypatch.setattr(calendar_handler.db_service, "get_available_days_in_range", fake_days)
        monkeypatch.setattr(calendar_handler.conversation_manager, "update_context", fake_update)

        response = await calendar_handler.handle_booking_current_week(
            1,
            "tg:1",
            3,
            {"pending_data": {"service": "Corte"}},
            reset_stack=True,
        )

        assert "Esta semana" in response
        assert "miércoles 3" in response
        assert "8) Buscar en otro mes" in response
        assert captured["state"] == "booking_current_week"
        assert captured["state_stack"] == []
        assert captured["pending_data"]["service_id"] == 3

    asyncio.run(_run())


def test_current_week_no_availability_jumps_to_month(monkeypatch):
    async def _run():
        states = []

        async def fake_days(**kwargs):
            start = kwargs["start_date"]
            if start == date(2026, 6, 1):
                return []
            return [{"date": "2026-07-02", "slot_count": 1, "label": "jueves 2"}]

        async def fake_update(_bid, _user, payload):
            states.append(payload["state"])

        monkeypatch.setattr(calendar_handler, "_today", lambda: date(2026, 6, 1))
        monkeypatch.setattr(calendar_handler.db_service, "get_available_days_in_range", fake_days)
        monkeypatch.setattr(calendar_handler.conversation_manager, "update_context", fake_update)

        response = await calendar_handler.handle_booking_current_week(
            1,
            "tg:1",
            3,
            {"pending_data": {"service": "Corte"}},
        )

        assert "¿En qué mes" in response
        assert states[-1] == "booking_month"

    asyncio.run(_run())


def test_month_list_shows_only_available_months(monkeypatch):
    async def _run():
        captured = {}

        async def fake_days(**kwargs):
            if kwargs["start_date"] == date(2026, 7, 1):
                return [{"date": "2026-07-02", "slot_count": 1, "label": "jueves 2"}]
            return []

        async def fake_update(_bid, _user, payload):
            captured.update(payload)

        monkeypatch.setattr(calendar_handler, "_today", lambda: date(2026, 6, 1))
        monkeypatch.setattr(calendar_handler.db_service, "get_available_days_in_range", fake_days)
        monkeypatch.setattr(calendar_handler.conversation_manager, "update_context", fake_update)

        response = await calendar_handler.handle_booking_month(
            1,
            "tg:1",
            {"pending_data": {"service_id": 3}},
        )

        assert "Julio 2026" in response
        assert "Agosto 2026" not in response
        assert captured["pending_data"]["calendar_months"] == [
            {"index": 1, "year": 2026, "month": 7, "label": "Julio 2026"}
        ]

    asyncio.run(_run())


def test_month_selection_transitions_to_week(monkeypatch):
    async def _run():
        captured = {}

        async def fake_days(**kwargs):
            if kwargs["start_date"] <= date(2026, 7, 7) and kwargs["end_date"] >= date(2026, 7, 2):
                return [{"date": "2026-07-02", "slot_count": 1, "label": "jueves 2"}]
            return []

        async def fake_update(_bid, _user, payload):
            captured.update(payload)

        monkeypatch.setattr(calendar_handler.db_service, "get_available_days_in_range", fake_days)
        monkeypatch.setattr(calendar_handler.conversation_manager, "update_context", fake_update)

        response = await calendar_handler.handle_booking_week(
            1,
            "tg:1",
            1,
            {
                "pending_data": {
                    "service_id": 3,
                    "calendar_months": [{"index": 1, "year": 2026, "month": 7, "label": "Julio 2026"}],
                }
            },
        )

        assert "Semana" in response
        assert captured["state"] == "booking_week"
        assert captured["pending_data"]["calendar_weeks"]

    asyncio.run(_run())


def test_week_selection_transitions_to_day(monkeypatch):
    async def _run():
        captured = {}

        async def fake_days(**_kwargs):
            return [{"date": "2026-07-02", "slot_count": 1, "label": "jueves 2"}]

        async def fake_update(_bid, _user, payload):
            captured.update(payload)

        monkeypatch.setattr(calendar_handler.db_service, "get_available_days_in_range", fake_days)
        monkeypatch.setattr(calendar_handler.conversation_manager, "update_context", fake_update)

        response = await calendar_handler.handle_booking_day(
            1,
            "tg:1",
            1,
            {
                "pending_data": {
                    "service_id": 3,
                    "calendar_weeks": [
                        {"index": 1, "start": "2026-07-01", "end": "2026-07-07", "label": "Semana del 1 al 7"}
                    ],
                }
            },
        )

        assert "¿Qué día" in response
        assert "jueves 2" in response
        assert captured["state"] == "booking_day"

    asyncio.run(_run())


def test_day_selection_saves_date_and_continues_to_slots(monkeypatch):
    async def _run():
        captured = {}

        async def fake_get_services(_bid):
            return [{"id": 3, "name": "Corte", "price": 10, "duration_minutes": 30}]

        async def fake_get_availability(**_kwargs):
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-07-02T10:00:00",
                        "end_datetime": "2026-07-02T10:30:00",
                    }
                ]
            }

        async def fake_update(_bid, _user, payload):
            captured.update(payload)

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 8,
            "customer_name": "Ana",
            "pending_data": {
                "service": "Corte",
                "service_id": 3,
                "calendar_days": [{"date": "2026-07-02", "slot_count": 1, "label": "jueves 2"}],
            },
        }
        selected = calendar_handler.selected_calendar_day(context, "1")
        response = await booking_handler.handle_book_appointment(
            {"entities": {"date": selected["date"]}, "_raw_user_text": "1"},
            {**context, "pending_data": {**context["pending_data"], "date": selected["date"]}},
        )

        assert "tenemos estos horarios" in response.lower()
        assert captured["state"] == "awaiting_slot_selection"
        assert captured["pending_data"]["date"] == "2026-07-02"

    asyncio.run(_run())


def test_calendar_to_slot_confirmation_creates_appointment(monkeypatch):
    async def _run():
        state = {}
        created = {"called": False}

        async def fake_get_services(_bid):
            return [{"id": 3, "name": "Corte", "price": 10, "duration_minutes": 30}]

        async def fake_get_availability(**_kwargs):
            return {
                "available_slots": [
                    {
                        "start_time": "10:00 AM",
                        "start_datetime": "2026-07-02T10:00:00",
                        "end_datetime": "2026-07-02T10:30:00",
                    }
                ]
            }

        async def fake_create_appointment(_data):
            created["called"] = True
            return {"id": 42}

        async def fake_get_business(_business_id):
            return {"name": "Barbería", "address": "Calle 1"}

        async def fake_update(_bid, _user, payload):
            state.update(payload)

        async def fake_clear(_bid, _user):
            state.update({"state": "idle", "pending_data": {}})

        monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_get_services)
        monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_get_availability)
        monkeypatch.setattr(booking_handler.db_service, "create_appointment", fake_create_appointment)
        monkeypatch.setattr(booking_handler.db_service, "get_business", fake_get_business)
        monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)
        monkeypatch.setattr(booking_handler.conversation_manager, "clear_pending_data", fake_clear)

        base_context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 8,
            "customer_name": "Ana",
            "pending_data": {
                "service": "Corte",
                "service_id": 3,
                "calendar_days": [{"date": "2026-07-02", "slot_count": 1, "label": "jueves 2"}],
                "date": "2026-07-02",
            },
        }

        await booking_handler.handle_book_appointment(
            {"entities": {"date": "2026-07-02"}, "_raw_user_text": "1"},
            base_context,
        )
        slot_context = {**base_context, "pending_data": dict(state["pending_data"])}
        await booking_handler.handle_slot_selection(
            {"entities": {}, "_raw_user_text": "1"},
            slot_context,
        )
        confirm_context = {**base_context, "pending_data": dict(state["pending_data"])}
        response = await booking_handler.handle_booking_confirmation(
            {"_raw_user_text": "sí"},
            confirm_context,
        )

        assert created["called"] is True
        assert "confirmada" in response.lower()

    asyncio.run(_run())


def test_calendar_input_invalid_increments_attempt_counter(monkeypatch):
    async def _run():
        state = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 8,
            "customer_name": "Ana",
            "current_intent": "book_appointment",
            "state": "booking_month",
            "pending_data": {"service_id": 3},
            "attempts": {"booking_month": 2},
            "state_stack": [],
        }

        async def fake_days(**_kwargs):
            return [{"date": "2026-07-02", "slot_count": 1, "label": "jueves 2"}]

        async def fake_save(*_args, **_kwargs):
            return None

        async def fake_get_context(_bid, _user):
            return dict(state)

        async def fake_update(_bid, _user, payload):
            state.update(payload)

        async def fail_nlu(*_args, **_kwargs):
            raise AssertionError("Calendar states must not call NLU")

        monkeypatch.setattr(calendar_handler, "_today", lambda: date(2026, 6, 1))
        monkeypatch.setattr(calendar_handler.db_service, "get_available_days_in_range", fake_days)
        monkeypatch.setattr(calendar_handler.conversation_manager, "update_context", fake_update)
        monkeypatch.setattr(orch.conversation_manager, "save_message", fake_save)
        monkeypatch.setattr(orch.conversation_manager, "get_context", fake_get_context)
        monkeypatch.setattr(orch.conversation_manager, "update_context", fake_update)
        monkeypatch.setattr(orch.nlu_engine, "process", fail_nlu)

        response = await orch.run_conversation_turn(1, "tg:1", "hola")

        assert "menú" in response.lower() or "menu" in response.lower()
        assert state["state"] == "idle"
        assert state["attempts"] == {}

    asyncio.run(_run())


def test_calendar_zero_goes_to_main_menu(monkeypatch):
    async def _run():
        state = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 8,
            "customer_name": "Ana",
            "current_intent": "book_appointment",
            "state": "booking_day",
            "pending_data": {"service_id": 3},
            "attempts": {},
            "state_stack": ["booking_week"],
        }

        async def fake_save(*_args, **_kwargs):
            return None

        async def fake_get_context(_bid, _user):
            return dict(state)

        async def fake_update(_bid, _user, payload):
            state.update(payload)

        monkeypatch.setattr(orch.conversation_manager, "save_message", fake_save)
        monkeypatch.setattr(orch.conversation_manager, "get_context", fake_get_context)
        monkeypatch.setattr(orch.conversation_manager, "update_context", fake_update)

        response = await orch.run_conversation_turn(1, "tg:1", "0")

        assert "1" in response
        assert state["state"] == "idle"
        assert state["pending_data"] == {}

    asyncio.run(_run())


def test_calendar_back_from_first_state_returns_idle(monkeypatch):
    async def _run():
        state = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 8,
            "customer_name": "Ana",
            "current_intent": "book_appointment",
            "state": "booking_current_week",
            "pending_data": {"service_id": 3},
            "attempts": {},
            "state_stack": [],
        }

        async def fake_save(*_args, **_kwargs):
            return None

        async def fake_get_context(_bid, _user):
            return dict(state)

        async def fake_update(_bid, _user, payload):
            state.update(payload)

        monkeypatch.setattr(orch.conversation_manager, "save_message", fake_save)
        monkeypatch.setattr(orch.conversation_manager, "get_context", fake_get_context)
        monkeypatch.setattr(orch.conversation_manager, "update_context", fake_update)

        await orch.run_conversation_turn(1, "tg:1", "9")

        assert state["state"] == "idle"
        assert state["pending_data"] == {}

    asyncio.run(_run())
