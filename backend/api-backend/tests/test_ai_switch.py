"""
Tests del interruptor único de IA (AI_ENABLED + OPENAI_API_KEY = config.ai_enabled).

Cubre: creación del cliente OpenAI, gateo de uses_ai en el router guiado,
cuota diaria de IA, y textos que prometen lenguaje natural.
"""
from datetime import datetime, timezone

import pytest

from app.config import config
from app.services import rate_limit_async
from app.services.guided_menu_router import route_guided_message
from app.services.nlu_engine import NLUEngine
from app.utils.conversation_routing import guided_menu


def ctx(state="idle", **extra):
    base = {
        "business_id": 1,
        "phone_number": "w:1",
        "state": state,
        "current_intent": None,
        "customer_id": 1,
        "customer_name": "Ana",
        "pending_data": {},
        "recent_messages": [],
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }
    base.update(extra)
    return base


# ── Creación del cliente OpenAI según el interruptor ──

def test_nlu_client_none_when_key_set_but_flag_off(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", False)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-dummy")
    engine = NLUEngine()
    assert engine.client is None


def test_nlu_client_none_when_flag_on_but_no_key(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    engine = NLUEngine()
    assert engine.client is None


def test_nlu_client_created_when_flag_and_key_present(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-dummy")
    engine = NLUEngine()
    assert engine.client is not None


# ── uses_ai en el router guiado según el interruptor ──

def test_uses_ai_false_in_all_paths_with_flag_off(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", False)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-dummy")

    d = route_guided_message("quiero cita mañana", ctx())
    assert d.kind == "direct_shortcut"
    assert d.uses_ai is False

    d = route_guided_message("necesito ayuda con algo raro", ctx())
    assert d.kind == "pass_to_nlu"
    assert d.uses_ai is False

    d = route_guided_message("el primero", ctx(state="awaiting_slot_selection"))
    assert d.kind == "active_flow"
    assert d.uses_ai is False


def test_uses_ai_true_in_all_paths_with_flag_on(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-dummy")

    assert route_guided_message("quiero cita mañana", ctx()).uses_ai is True
    assert route_guided_message("necesito ayuda con algo raro", ctx()).uses_ai is True
    assert route_guided_message("el primero", ctx(state="awaiting_slot_selection")).uses_ai is True


# ── Cuota diaria de IA: con flag off no se consume ──

@pytest.mark.asyncio
async def test_quota_ai_not_consumed_with_flag_off(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AI_ENABLED", False)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "DISABLE_USAGE_LIMITS", False)
    monkeypatch.setattr(rate_limit_async, "_daily_file_path", str(tmp_path / "quota.json"))

    r1 = await rate_limit_async.consume_daily_quota(
        business_id=1, user_channel_id="u1", is_ai_message=True
    )
    assert r1["allowed"] is True
    assert r1["ai_count"] is None  # no se contó como mensaje de IA

    # Con flag on, el mismo mensaje sí consume cuota de IA
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-dummy")
    r2 = await rate_limit_async.consume_daily_quota(
        business_id=1, user_channel_id="u1", is_ai_message=True
    )
    assert r2["ai_count"] == 1


# ── Textos: sin flag no se promete lenguaje natural ──

def test_guided_menu_hides_direct_request_with_flag_off(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", False)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    text = guided_menu("Ana")
    assert "pedido directo" not in text
    assert "1) Agendar cita" in text


def test_guided_menu_shows_direct_request_with_flag_on(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-dummy")
    text = guided_menu("Ana")
    assert "pedido directo" in text


@pytest.mark.asyncio
async def test_welcome_hides_natural_language_with_flag_off(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", False)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    sent = []

    async def fake_get_business(_bid):
        return {"name": "Barbería Test"}

    async def fake_send(chat_id, message):
        sent.append(message)

    async def noop(*_args, **_kwargs):
        pass

    monkeypatch.setattr(
        "app.services.telegram_inbound.db_service.get_business", fake_get_business
    )
    monkeypatch.setattr(
        "app.services.telegram_inbound.telegram_client.send_text_message", fake_send
    )
    monkeypatch.setattr("app.services.telegram_inbound._after_welcome_onboarding", noop)

    from app.services.telegram_inbound import _send_welcome_for_business

    await _send_welcome_for_business(1, "chat-1")
    assert len(sent) == 1
    assert "lenguaje natural" not in sent[0]
    assert "menú" in sent[0]


@pytest.mark.asyncio
async def test_welcome_shows_natural_language_with_flag_on(monkeypatch):
    monkeypatch.setattr(config, "AI_ENABLED", True)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "sk-test-dummy")
    sent = []

    async def fake_get_business(_bid):
        return {"name": "Barbería Test"}

    async def fake_send(chat_id, message):
        sent.append(message)

    async def noop(*_args, **_kwargs):
        pass

    monkeypatch.setattr(
        "app.services.telegram_inbound.db_service.get_business", fake_get_business
    )
    monkeypatch.setattr(
        "app.services.telegram_inbound.telegram_client.send_text_message", fake_send
    )
    monkeypatch.setattr("app.services.telegram_inbound._after_welcome_onboarding", noop)

    from app.services.telegram_inbound import _send_welcome_for_business

    await _send_welcome_for_business(1, "chat-1")
    assert len(sent) == 1
    assert "lenguaje natural" in sent[0]
