"""
telegram_inbound serializa BotReply.keyboard a reply_markup.inline_keyboard
y muestra el menú principal con teclado en bienvenida / captura de nombre.

Desde F3b cada teclado se envía con token de pantalla (callback_data|token)
y el token rota en cada envío (screen_token en el contexto).
"""
import pytest

from app.services import telegram_inbound
from app.utils import telegram_ui


def _capture_send(monkeypatch, sent):
    async def fake_send_text_message(*_a, **kwargs):
        sent.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(telegram_inbound.telegram_client, "send_text_message", fake_send_text_message)


def _base_mocks(monkeypatch, captured=None):
    async def fake_binding(_user_id):
        return 1

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": [], "customer_name": "Ana"}

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(_bid, _key, payload):
        if captured is not None:
            captured.setdefault("updates", []).append(payload)
        return None

    monkeypatch.setattr(telegram_inbound, "get_binding_business_id", fake_binding)
    monkeypatch.setattr(telegram_inbound.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(telegram_inbound.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(telegram_inbound.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr("app.services.rate_limit_async.consume_daily_quota", fake_quota)


def _screen_token(captured):
    """Último screen_token persistido por _send_bot_reply en los update_context."""
    for update in reversed(captured["updates"]):
        if "screen_token" in update:
            return update["screen_token"]
    return None


def _screen_tokens(captured):
    """Todos los screen_token persistidos, en orden de envío."""
    return [update["screen_token"] for update in captured["updates"] if "screen_token" in update]


async def test_telegram_greeting_sends_main_menu_keyboard(monkeypatch):
    sent = []
    captured = {}
    _base_mocks(monkeypatch, captured)
    _capture_send(monkeypatch, sent)
    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {"from": "123", "text": "hola"},
    )

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu greeting")

    monkeypatch.setattr(telegram_inbound, "_run_nlu_pipeline", fail_nlu)

    resp = await telegram_inbound.process_telegram_update({"message": {"text": "hola"}})

    assert resp.get("status") == "ok"
    last = sent[-1]
    token = _screen_token(captured)
    assert token and len(token) == 8
    assert last["reply_markup"]["inline_keyboard"] == telegram_ui.with_screen_token(
        telegram_ui.main_menu_keyboard(), token
    )


async def test_telegram_callback_nav_menu_sends_main_menu_keyboard(monkeypatch):
    sent = []
    captured = {}
    _base_mocks(monkeypatch, captured)
    _capture_send(monkeypatch, sent)
    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "from": "123",
            "type": "interactive",
            "button_payload": "nav_menu",
            "text": "nav_menu",
        },
    )

    async def fail_nlu(*_a, **_k):
        raise AssertionError("Callback nav_menu must be handled by the guided router")

    monkeypatch.setattr(telegram_inbound, "_run_nlu_pipeline", fail_nlu)

    resp = await telegram_inbound.process_telegram_update({"message": {"text": "nav_menu"}})

    assert resp.get("status") == "ok"
    last = sent[-1]
    token = _screen_token(captured)
    assert token and len(token) == 8
    assert last["reply_markup"]["inline_keyboard"] == telegram_ui.with_screen_token(
        telegram_ui.main_menu_keyboard(), token
    )
    assert "ya no está vigente" not in last["message"]


async def test_screen_token_rotates_between_consecutive_sends(monkeypatch):
    sent = []
    captured = {}
    _base_mocks(monkeypatch, captured)
    _capture_send(monkeypatch, sent)
    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {"from": "123", "text": "hola"},
    )

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu greeting")

    monkeypatch.setattr(telegram_inbound, "_run_nlu_pipeline", fail_nlu)

    await telegram_inbound.process_telegram_update({"message": {"text": "hola"}})
    await telegram_inbound.process_telegram_update({"message": {"text": "hola"}})

    tokens = _screen_tokens(captured)
    assert len(sent) == 2
    assert len(tokens) == 2, f"expected two screen_token rotations, got {tokens}"
    assert tokens[0] != tokens[1], "el token debe rotar entre envíos consecutivos"
    for i, token in enumerate(tokens):
        assert sent[i]["reply_markup"]["inline_keyboard"] == telegram_ui.with_screen_token(
            telegram_ui.main_menu_keyboard(), token
        )
