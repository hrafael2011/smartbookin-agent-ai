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
        assert "cuándo" in r1.lower() or "cuando" in r1.lower()
        assert captured["last"]["pending_data"].get("service") == "Corte"

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
