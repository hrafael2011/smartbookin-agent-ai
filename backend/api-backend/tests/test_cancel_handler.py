import asyncio

from app.handlers import cancel_handler


def test_cancel_selection_allows_exit_without_number(monkeypatch):
    async def _run():
        cleared = {"called": False}

        async def fake_get_appointments(*_args, **_kwargs):
            return [
                {"id": 1, "start_at": "2026-04-13T10:00:00", "service_name": "Cerquillos"},
                {"id": 2, "start_at": "2026-04-14T10:30:00", "service_name": "Cejas"},
            ]

        async def fake_clear(*_args, **_kwargs):
            cleared["called"] = True
            return None

        monkeypatch.setattr(cancel_handler.db_service, "get_customer_appointments", fake_get_appointments)
        monkeypatch.setattr(cancel_handler.conversation_manager, "clear_pending_data", fake_clear)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "state": "awaiting_appointment_selection",
            "pending_data": {},
        }
        nlu = {"_raw_user_text": "ninguna cita", "entities": {}}
        resp = await cancel_handler.handle_cancel_appointment(nlu, context)

        assert cleared["called"] is True
        assert "no cancelé ninguna cita" in resp.lower()

    asyncio.run(_run())


def test_cancel_selection_can_show_menu(monkeypatch):
    async def _run():
        cleared = {"called": False}

        async def fake_get_appointments(*_args, **_kwargs):
            return [
                {"id": 1, "start_at": "2026-04-13T10:00:00", "service_name": "Cerquillos"},
                {"id": 2, "start_at": "2026-04-14T10:30:00", "service_name": "Cejas"},
            ]

        async def fake_clear(*_args, **_kwargs):
            cleared["called"] = True
            return None

        monkeypatch.setattr(cancel_handler.db_service, "get_customer_appointments", fake_get_appointments)
        monkeypatch.setattr(cancel_handler.conversation_manager, "clear_pending_data", fake_clear)

        context = {
            "business_id": 1,
            "phone_number": "tg:1",
            "customer_id": 7,
            "customer_name": "Ana",
            "state": "awaiting_appointment_selection",
            "pending_data": {},
        }
        nlu = {"_raw_user_text": "ya no quiero cancelar la cita, quiero que me muestres el menu inicial", "entities": {}}
        resp = await cancel_handler.handle_cancel_appointment(nlu, context)

        assert cleared["called"] is True
        assert "podés elegir una opción" in resp.lower()

    asyncio.run(_run())
