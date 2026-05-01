import pytest

import main
import app.services.telegram_inbound as telegram_inbound


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

    async def fake_send_text_message(*_a, **_k):
        return {"messages": [{"id": "out.1"}]}

    async def fake_consume_daily_quota(*_a, **_k):
        return {"allowed": True}

    async def fail_nlu(*_a, **_k):
        raise AssertionError("NLU should not run for deterministic menu greeting")

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
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
        telegram_inbound.telegram_client,
        "send_text_message",
        fake_send_text_message,
    )
    monkeypatch.setattr("app.services.rate_limit_async.consume_daily_quota", fake_quota)
    monkeypatch.setattr(telegram_inbound, "_run_nlu_pipeline", fail_nlu)

    resp = await telegram_inbound.process_telegram_update({"message": {"text": "hola"}})

    assert resp.get("status") == "ok"
    assert sent_messages
    assert "1) Agendar cita" in sent_messages[-1]


async def test_whatsapp_duplicate_message_is_ignored_after_first_processing(monkeypatch):
    sent_messages = []
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


async def test_whatsapp_ai_quota_exhausted_still_allows_deterministic_menu(monkeypatch):
    sent_messages = []
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

    async def fake_send_text_message(*_a, **kwargs):
        sent_messages.append(kwargs.get("message") or "")
        return {"messages": [{"id": "out.1"}]}

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
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)
    monkeypatch.setattr(main, "consume_daily_quota", fake_quota)
    monkeypatch.setattr(main, "run_conversation_turn", fail_nlu)

    resp = await main.whatsapp_webhook(
        DummyRequest({}, headers={"X-Hub-Signature-256": "sha256=ok"})
    )

    assert resp.get("status") == "ok"
    assert quota_calls[-1]["is_ai_message"] is False
    assert "1) Agendar cita" in sent_messages[-1]


async def test_whatsapp_total_quota_blocks_even_deterministic_menu(monkeypatch):
    sent_messages = []

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
