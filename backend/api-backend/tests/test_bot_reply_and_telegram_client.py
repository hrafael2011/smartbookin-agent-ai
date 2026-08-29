"""
BotReply: respuesta de bot que ES un str y además lleva teclado inline opcional.
telegram_client: serializa el teclado a reply_markup.inline_keyboard.
"""
import asyncio

from importlib import import_module

from app.core.response_builder import BotReply
from app.services.telegram_client import telegram_client

# app/services/__init__ re-exporta el singleton con el mismo nombre que el submódulo,
# por lo que `import ... as` se queda con la instancia; import_module resuelve el módulo real.
telegram_client_module = import_module("app.services.telegram_client")


# ── BotReply ─────────────────────────────────────────────────────────────────

def test_bot_reply_is_str_with_keyboard():
    reply = BotReply("Hola", keyboard=[[{"text": "Sí", "callback_data": "confirm_yes"}]])

    assert isinstance(reply, str)
    assert reply == "Hola"
    assert reply.keyboard == [[{"text": "Sí", "callback_data": "confirm_yes"}]]


def test_bot_reply_without_keyboard_has_none():
    reply = BotReply("Solo texto")
    assert reply.keyboard is None


def test_bot_reply_works_in_string_contexts():
    reply = BotReply("Elegí una opción")
    assert "opción" in reply
    assert reply.lower().startswith("elegí")


# ── telegram_client ──────────────────────────────────────────────────────────

def _capture_post(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, **kwargs):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(telegram_client_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(telegram_client_module.config, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(
        telegram_client_module.config,
        "TELEGRAM_API_BASE_URL",
        "https://api.telegram.org/bottest-token",
    )
    return captured


def test_send_text_message_without_reply_markup_omits_key(monkeypatch):
    captured = _capture_post(monkeypatch)

    asyncio.run(telegram_client.send_text_message("123", "Hola"))

    assert "reply_markup" not in captured["json"]
    assert captured["json"]["chat_id"] == "123"
    assert captured["json"]["text"] == "Hola"


def test_send_text_message_includes_reply_markup(monkeypatch):
    captured = _capture_post(monkeypatch)
    keyboard = [[{"text": "Sí", "callback_data": "confirm_yes"}]]

    asyncio.run(
        telegram_client.send_text_message(
            "123", "¿Confirmo?", reply_markup={"inline_keyboard": keyboard}
        )
    )

    assert captured["json"]["reply_markup"] == {"inline_keyboard": keyboard}


def test_send_inline_keyboard_builds_rows(monkeypatch):
    captured = _capture_post(monkeypatch)
    rows = [
        [{"text": "Corte", "callback_data": "service_1"}],
        [{"text": "🔙 Volver", "callback_data": "nav_back"}],
    ]

    asyncio.run(telegram_client.send_inline_keyboard("123", "¿Qué servicio?", rows))

    assert captured["json"]["reply_markup"]["inline_keyboard"] == rows
    assert captured["json"]["text"] == "¿Qué servicio?"
