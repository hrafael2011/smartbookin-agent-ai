"""
Pantallas del flujo de agendamiento con teclados inline (booking_handler).

- Confirmación: botones [✅ Confirmar][🔁 Ver otro horario] + footer.
- Horarios: grilla de 3 columnas + footer.
- Días sugeridos: botones day_* + footer.
- Pregunta de servicio: botones service_* + footer.
- Confirmación exitosa: menú principal con teclado + mark_main_menu.
"""
from importlib import import_module

import pytest

from app.core.response_builder import BotReply
from app.handlers import booking_handler
from app.utils import telegram_ui

# app/services/__init__ re-exporta el singleton con el mismo nombre que el submódulo
cm_module = import_module("app.services.conversation_manager")


def _slot(hour=9, minute=0):
    return {
        "start_time": f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}",
        "start_datetime": f"2026-08-28T{hour:02d}:{minute:02d}:00+00:00",
        "end_datetime": f"2026-08-28T{hour:02d}:{minute + 15:02d}:00+00:00",
    }


def test_confirmation_screen_has_buttons_and_footer():
    reply = booking_handler._build_confirmation_text(
        "Ana", "Corte", "2026-08-28", _slot(hour=9)
    )

    assert isinstance(reply, BotReply)
    assert "¿Confirmo esta cita?" in reply
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["confirm_yes", "confirm_no"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]


@pytest.mark.asyncio
async def test_booking_slots_screen_uses_time_grid(monkeypatch):
    captured = {}

    async def fake_services(_bid):
        return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

    async def fake_availability(**_kwargs):
        return {"available_slots": [_slot(hour=9), _slot(hour=9, minute=15), _slot(hour=9, minute=30)]}

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_availability)
    monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

    nlu = {"_raw_user_text": "", "entities": {}, "missing": []}
    context = {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {"date": "2026-08-28", "service": "Corte", "service_id": 1},
    }
    reply = await booking_handler.handle_book_appointment(nlu, context)

    assert isinstance(reply, BotReply)
    # Sin lista numerada en el texto
    assert "1. 9:00 AM" not in reply
    # Grilla de 3 columnas con callback time_*
    assert [b["callback_data"] for b in reply.keyboard[0]] == [
        "time_2026-08-28_09:00",
        "time_2026-08-28_09:15",
        "time_2026-08-28_09:30",
    ]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
    assert captured["update"]["state"] == "awaiting_slot_selection"


@pytest.mark.asyncio
async def test_suggested_days_screen_has_day_buttons_and_footer(monkeypatch):
    captured = {}

    async def fake_services(_bid):
        return [{"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30}]

    async def fake_availability(**_kwargs):
        return {"available_slots": []}

    async def fake_next_days(*_a, **_k):
        return [{"date": "2026-08-29"}, {"date": "2026-08-30"}]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_availability)
    monkeypatch.setattr(booking_handler.db_service, "get_next_available_days", fake_next_days)
    monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

    nlu = {"_raw_user_text": "", "entities": {}, "missing": []}
    context = {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {"date": "2026-08-28", "service": "Corte"},
    }
    reply = await booking_handler.handle_book_appointment(nlu, context)

    assert isinstance(reply, BotReply)
    assert reply.keyboard[0][0]["callback_data"] == "day_2026-08-29"
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]
    assert captured["update"]["pending_data"]["suggested_days"]


@pytest.mark.asyncio
async def test_service_question_screen_has_service_buttons_and_footer(monkeypatch):
    captured = {}

    async def fake_services(_bid):
        return [
            {"id": 1, "name": "Corte", "price": 10, "duration_minutes": 30},
            {"id": 2, "name": "Barba", "price": 8, "duration_minutes": 15},
        ]

    async def fake_update(_b, _k, payload):
        captured["update"] = payload

    monkeypatch.setattr(booking_handler.db_service, "get_business_services", fake_services)
    monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)

    nlu = {"_raw_user_text": "no sé cuál", "entities": {}, "missing": []}
    context = {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {"date": "2026-08-28", "selected_slot": _slot(hour=9)},
    }
    reply = await booking_handler.handle_book_appointment(nlu, context)

    assert isinstance(reply, BotReply)
    assert [b["callback_data"] for b in reply.keyboard[0]] == ["service_1", "service_2"]
    assert [b["callback_data"] for b in reply.keyboard[-1]] == ["nav_back", "nav_menu", "nav_exit"]


@pytest.mark.asyncio
async def test_booking_confirmation_success_returns_main_menu_keyboard(monkeypatch):
    captured = {}

    async def fake_availability(**_kwargs):
        return {"available_slots": [_slot(hour=9)]}

    async def fake_create(appointment_data):
        captured["created"] = appointment_data
        return {"id": 55}

    async def fake_business(_bid):
        return {"name": "Barbería", "address": "Calle 1"}

    async def fake_update(*_a, **_k):
        return None

    async def fake_mark(*_a, **_k):
        captured["marked"] = True
        return None

    monkeypatch.setattr(booking_handler.db_service, "get_availability", fake_availability)
    monkeypatch.setattr(booking_handler.db_service, "create_appointment", fake_create)
    monkeypatch.setattr(booking_handler.db_service, "get_business", fake_business)
    monkeypatch.setattr(booking_handler.conversation_manager, "update_context", fake_update)
    monkeypatch.setattr(
        cm_module.conversation_manager, "mark_main_menu", fake_mark
    )

    nlu = {"_raw_user_text": "sí", "entities": {}, "missing": []}
    context = {
        "business_id": 1,
        "phone_number": "tg:1",
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {
            "date": "2026-08-28",
            "service": "Corte",
            "service_id": 1,
            "selected_slot": _slot(hour=9),
        },
    }
    reply = await booking_handler.handle_booking_confirmation(nlu, context)

    assert "¡Tu cita está confirmada!" in reply
    assert captured["created"]["customer"] == 1
    assert reply.keyboard == telegram_ui.main_menu_keyboard()
    assert captured.get("marked") is True
