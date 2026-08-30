import pytest
from fastapi import HTTPException

import main
import app.services.guided_menu_router as guided_menu_router
import app.services.telegram_inbound as telegram_inbound
from app.core.response_builder import BotReply
from app.services.guided_menu_router import RouteDecision
from app.utils.telegram_ui import main_menu_reply


@pytest.fixture(autouse=True)
def allow_channel_idempotency(monkeypatch):
    async def fake_should_process(*_a, **_k):
        return True

    async def fake_owner_binding(_telegram_user_id):
        return None

    monkeypatch.setattr(main, "should_process_channel_event", fake_should_process)
    monkeypatch.setattr(
        telegram_inbound,
        "should_process_channel_event",
        fake_should_process,
    )
    monkeypatch.setattr(
        telegram_inbound,
        "get_owner_binding_by_telegram_user_id",
        fake_owner_binding,
    )


class DummyRequest:
    def __init__(self, payload, body=b"{}", headers=None, query_params=None):
        self._payload = payload
        self._body = body
        self.headers = headers or {}
        self.query_params = query_params or {}

    async def json(self):
        return self._payload

    async def body(self):
        return self._body


async def test_whatsapp_verify_returns_raw_challenge_string(monkeypatch):
    monkeypatch.setattr(main.config, "META_VERIFY_TOKEN", "verify_abc")
    req = DummyRequest(
        None,
        query_params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify_abc",
            "hub.challenge": "12345",
        },
    )
    resp = await main.verify_webhook(req)
    assert resp.body == b"12345"
    assert resp.media_type == "text/plain"


async def test_whatsapp_verify_accepts_alphanumeric_challenge(monkeypatch):
    monkeypatch.setattr(main.config, "META_VERIFY_TOKEN", "verify_abc")
    req = DummyRequest(
        None,
        query_params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify_abc",
            "hub.challenge": "abc123",
        },
    )
    resp = await main.verify_webhook(req)
    assert resp.body == b"abc123"


async def test_whatsapp_verify_rejects_bad_token(monkeypatch):
    monkeypatch.setattr(main.config, "META_VERIFY_TOKEN", "verify_abc")
    req = DummyRequest(
        None,
        query_params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "12345",
        },
    )
    with pytest.raises(HTTPException) as exc:
        await main.verify_webhook(req)
    assert exc.value.status_code == 403


async def test_telegram_webhook_endpoint_ok(monkeypatch):
    async def fake_process(_payload):
        return {"status": "ok"}

    monkeypatch.setattr(main, "process_telegram_update", fake_process)
    resp = await main.telegram_webhook(
        DummyRequest({"message": {"chat": {"id": 1}, "text": "hola"}})
    )
    assert resp.get("status") == "ok"


async def test_whatsapp_webhook_endpoint_ok(monkeypatch):
    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.1",
            "from": "18095550000",
            "text": "hola",
            "type": "text",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_send_text_message(*_a, **_k):
        return {"messages": [{"id": "out.1"}]}

    async def fake_send_list_message(*_a, **_k):
        return {"messages": [{"id": "out.list"}]}

    async def fake_consume_daily_quota(*_a, **_k):
        return {"allowed": True}

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu greeting")

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(main.whatsapp_client, "send_list_message", fake_send_list_message)
    monkeypatch.setattr(main, "consume_daily_quota", fake_consume_daily_quota)
    monkeypatch.setattr(main, "run_conversation_turn", fail_nlu)

    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "WBID_TEST_001"},
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "18095550000",
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    resp = await main.whatsapp_webhook(
        DummyRequest(payload, headers={"X-Hub-Signature-256": "sha256=ok"})
    )
    assert resp.get("status") == "ok"


async def test_telegram_inbound_greeting_uses_guided_router_without_nlu(monkeypatch):
    sent_messages = []

    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {"from": "123", "text": "hola"},
    )

    async def fake_binding(_user_id):
        return 1

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_send_text_message(*_a, **kwargs):
        sent_messages.append(kwargs.get("message") or "")
        return {"ok": True}

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu greeting")

    monkeypatch.setattr(telegram_inbound, "get_binding_business_id", fake_binding)
    monkeypatch.setattr(
        telegram_inbound.conversation_manager,
        "get_context",
        fake_get_context,
    )
    monkeypatch.setattr(
        telegram_inbound.conversation_manager,
        "save_message",
        fake_save_message,
    )
    monkeypatch.setattr(
        telegram_inbound.conversation_manager,
        "update_context",
        fake_update_context,
    )
    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "send_text_message",
        fake_send_text_message,
    )
    monkeypatch.setattr("app.services.rate_limit_async.consume_daily_quota", fake_quota)
    monkeypatch.setattr(telegram_inbound, "_run_nlu_pipeline", fail_nlu)

    resp = await telegram_inbound.process_telegram_update({"message": {"text": "hola"}})

    assert resp.get("status") == "ok"
    assert sent_messages
    assert "Elegí una opción" in sent_messages[-1]


async def test_whatsapp_duplicate_message_is_ignored_after_first_processing(monkeypatch):
    sent_messages = []
    sent_kwargs = []
    calls = {"nlu": 0}

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.duplicate",
            "from": "18095550000",
            "text": "necesito algo complejo",
            "type": "text",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_send_text_message(*_a, **kwargs):
        sent_messages.append(kwargs.get("message") or "")
        sent_kwargs.append(kwargs)
        return {"messages": [{"id": "out.1"}]}

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fake_nlu(*_a, **_k):
        calls["nlu"] += 1
        return "NLU_OK"

    seen = set()

    async def fake_should_process(**kwargs):
        event_id = kwargs.get("event_id")
        if event_id in seen:
            return False
        seen.add(event_id)
        return True

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "run_conversation_turn", fake_nlu)
    monkeypatch.setattr(main, "should_process_channel_event", fake_should_process)

    payload = {"entry": [{"changes": [{"value": {"messages": [{"id": "wamid.duplicate"}]}}]}]}
    request = DummyRequest(payload, headers={"X-Hub-Signature-256": "sha256=ok"})

    first = await main.whatsapp_webhook(request)
    second = await main.whatsapp_webhook(request)

    assert first.get("status") == "ok"
    assert second.get("status") == "ok"
    assert calls["nlu"] == 1
    assert sent_messages == ["NLU_OK"]
    assert sent_kwargs[0].get("phone_number_id") == "WBID_TEST_001"


async def test_whatsapp_ai_quota_exhausted_still_allows_deterministic_menu(monkeypatch):
    sent_messages = []
    sent_lists = []
    quota_calls = []

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.quota.menu",
            "from": "18095550001",
            "text": "hola",
            "type": "text",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_send_text_message(*_a, **kwargs):
        sent_messages.append(kwargs.get("message") or "")
        return {"messages": [{"id": "out.1"}]}

    async def fake_send_list_message(*_a, **kwargs):
        sent_lists.append(kwargs)
        return {"messages": [{"id": "out.list"}]}

    async def fake_quota(**kwargs):
        quota_calls.append(kwargs)
        if kwargs.get("is_ai_message"):
            return {"allowed": False, "message": "Límite IA"}
        return {"allowed": True}

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu")

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(main.whatsapp_client, "send_list_message", fake_send_list_message)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "run_conversation_turn", fail_nlu)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert quota_calls[-1]["is_ai_message"] is False
    rows = [r["id"] for s in sent_lists[-1]["sections"] for r in s["rows"]]
    assert "menu_agendar" in rows
    assert "1) Agendar cita" not in sent_lists[-1]["body_text"]


async def test_whatsapp_total_quota_blocks_even_deterministic_menu(monkeypatch):
    sent_messages = []
    sent_kwargs = []

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.quota.total",
            "from": "18095550002",
            "text": "hola",
            "type": "text",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_send_text_message(*_a, **kwargs):
        sent_messages.append(kwargs.get("message") or "")
        sent_kwargs.append(kwargs)
        return {"messages": [{"id": "out.1"}]}

    async def fake_quota(*_a, **_k):
        return {"allowed": False, "message": "Límite total"}

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert sent_messages == ["Límite total"]
    assert sent_kwargs[-1].get("phone_number_id") == "WBID_TEST_001"


async def test_whatsapp_webhook_passes_tenant_phone_number_id_to_guided_send(monkeypatch):
    """El envío del menú guiado usa el phone_number_id del negocio resuelto (outbound multi-tenant)."""
    sent_kwargs = []
    sent_lists = []

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.pid",
            "from": "18095550000",
            "text": "hola",
            "type": "text",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_send_text_message(*_a, **kwargs):
        sent_kwargs.append(kwargs)
        return {"messages": [{"id": "out.1"}]}

    async def fake_send_list_message(*_a, **kwargs):
        sent_lists.append(kwargs)
        return {"messages": [{"id": "out.list"}]}

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu greeting")

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(main.whatsapp_client, "send_list_message", fake_send_list_message)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "run_conversation_turn", fail_nlu)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert sent_lists
    assert sent_lists[-1].get("phone_number_id") == "WBID_TEST_001"
    rows = [r["id"] for s in sent_lists[-1]["sections"] for r in s["rows"]]
    assert "menu_agendar" in rows


async def test_whatsapp_webhook_normalizes_from_phone(monkeypatch):
    """El `from` de Meta (E.164 con formato libre) se normaliza antes de usarse."""
    seen = {}

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.norm",
            "from": "+1 (809) 555-1234",
            "text": "hola",
            "type": "text",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_should_process(**kwargs):
        seen["idempotency_user_key"] = kwargs.get("user_key")
        return True

    async def fake_get_context(*args, **_k):
        seen["context_phone"] = args[1] if len(args) > 1 else None
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_send_text_message(*_a, **_k):
        return {"messages": [{"id": "out.1"}]}

    async def fake_send_list_message(*_a, **_k):
        return {"messages": [{"id": "out.list"}]}

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu greeting")

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main, "should_process_channel_event", fake_should_process)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(main.whatsapp_client, "send_list_message", fake_send_list_message)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "run_conversation_turn", fail_nlu)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert seen["idempotency_user_key"] == "18095551234"
    assert seen["context_phone"] == "18095551234"


async def test_whatsapp_button_reply_routes_by_id(monkeypatch):
    """El webhook rutea por el id del botón (no por su título visible)."""
    routed = {}

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.btn",
            "from": "18095550000",
            "type": "interactive",
            "text": "Agendar cita",  # título visible — NO debe usarse para rutear
            "button_payload": "menu_agendar",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    def fake_route(message_text, _context):
        routed["text"] = message_text
        return RouteDecision("inline_callback")

    async def fake_execute(*_a, **_k):
        return BotReply("OK")

    async def fake_send_text_message(*_a, **_k):
        return {"messages": [{"id": "out.1"}]}

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "route_guided_message", fake_route)
    monkeypatch.setattr(main, "execute_guided_route", fake_execute)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert routed["text"] == "menu_agendar"


async def test_whatsapp_list_reply_routes_by_id(monkeypatch):
    """El webhook rutea por el id de la fila de lista (list_reply)."""
    routed = {}

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.list",
            "from": "18095550000",
            "type": "interactive",
            "text": "Corte de cabello",  # título visible — NO debe usarse para rutear
            "list_payload": "service_3",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    def fake_route(message_text, _context):
        routed["text"] = message_text
        return RouteDecision("inline_callback")

    async def fake_execute(*_a, **_k):
        return BotReply("OK")

    async def fake_send_text_message(*_a, **_k):
        return {"messages": [{"id": "out.1"}]}

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "route_guided_message", fake_route)
    monkeypatch.setattr(main, "execute_guided_route", fake_execute)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert routed["text"] == "service_3"


async def test_whatsapp_interactive_reply_sends_interactive_response(monkeypatch):
    """Un toque de botón responde con interactive (list), no con texto plano."""
    sent_lists = []

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.menu",
            "from": "18095550000",
            "type": "interactive",
            "text": "Agendar cita",
            "button_payload": "menu_agendar",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fake_execute(*_a, **_k):
        return main_menu_reply()

    async def fake_send_list_message(*_a, **kwargs):
        sent_lists.append(kwargs)
        return {"messages": [{"id": "out.list"}]}

    async def fake_send_text_message(*_a, **_k):
        raise AssertionError("el menú con teclado debe ir como list message")

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "execute_guided_route", fake_execute)
    monkeypatch.setattr(main.whatsapp_client, "send_list_message", fake_send_list_message)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert sent_lists
    rows = [r["id"] for s in sent_lists[0]["sections"] for r in s["rows"]]
    assert "menu_agendar" in rows
    assert sent_lists[0]["phone_number_id"] == "WBID_TEST_001"


async def test_whatsapp_orphan_button_gets_stale_menu(monkeypatch):
    """Un callback inválido para el estado actual → 'ya no está vigente' + menú."""
    sent_lists = []

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.orphan",
            "from": "18095550000",
            "type": "interactive",
            "text": "9:00 AM",
            "button_payload": "time_2026-08-30_09:00",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    async def fake_send_list_message(*_a, **kwargs):
        sent_lists.append(kwargs)
        return {"messages": [{"id": "out.list"}]}

    async def fake_send_text_message(*_a, **_k):
        raise AssertionError("el stale debe renderizarse como list message")

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(guided_menu_router.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main.whatsapp_client, "send_list_message", fake_send_list_message)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert sent_lists
    assert "ya no está vigente" in sent_lists[0]["body_text"]
    rows = [r["id"] for s in sent_lists[0]["sections"] for r in s["rows"]]
    assert "menu_agendar" in rows


async def test_whatsapp_free_text_still_works(monkeypatch):
    """El texto libre (p.ej. 'menu') sigue funcionando y responde con lista."""
    sent_lists = []

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "message_id": "wamid.freetext",
            "from": "18095550000",
            "text": "menu",
            "type": "text",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    async def fake_get_business_by_phone_id(_pid):
        return {"id": 1, "name": "Demo"}

    async def fake_get_context(*_a, **_k):
        return {"state": "idle", "current_intent": None, "recent_messages": []}

    async def fake_quota(*_a, **_k):
        return {"allowed": True}

    async def fake_send_list_message(*_a, **kwargs):
        sent_lists.append(kwargs)
        return {"messages": [{"id": "out.list"}]}

    async def fake_send_text_message(*_a, **_k):
        raise AssertionError("el menú debe ir como list message")

    async def fake_save_message(*_a, **_k):
        return None

    async def fake_update_context(*_a, **_k):
        return None

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.conversation_manager, "update_context", fake_update_context)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main.whatsapp_client, "send_list_message", fake_send_list_message)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert sent_lists
    rows = [r["id"] for s in sent_lists[0]["sections"] for r in s["rows"]]
    assert "menu_agendar" in rows


async def test_whatsapp_status_update_is_logged_and_ignored(monkeypatch):
    """Los statuses de Meta (sent/delivered/failed) se loguean, no se procesan."""
    logs = []
    extract_calls = []

    monkeypatch.setattr(main.whatsapp_client, "validate_signature", lambda *_a, **_k: True)
    monkeypatch.setattr(
        main.whatsapp_client,
        "extract_message_from_webhook",
        lambda _payload: {
            "type": "status_update",
            "status": "failed",
            "message_id": "wamid.status1",
            "recipient_id": "18095550000",
            "business_phone_number_id": "WBID_TEST_001",
        },
    )

    async def fake_mark_as_read(*_a, **_k):
        return {"ok": True}

    def fake_logger_info(msg, *args, **kwargs):
        logs.append((msg, args))

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.logger, "info", fake_logger_info)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert any("wa_status_update" in msg for msg, _ in logs)
