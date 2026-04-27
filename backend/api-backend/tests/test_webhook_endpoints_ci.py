from fastapi.testclient import TestClient

import main


def test_telegram_webhook_endpoint_ok(monkeypatch):
    async def fake_process(_payload):
        return {"status": "ok"}

    monkeypatch.setattr(main, "process_telegram_update", fake_process)
    client = TestClient(main.app)
    resp = client.post("/webhooks/telegram", json={"message": {"chat": {"id": 1}, "text": "hola"}})
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_whatsapp_webhook_endpoint_ok(monkeypatch):
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

    monkeypatch.setattr(main.whatsapp_client, "mark_as_read", fake_mark_as_read)
    monkeypatch.setattr(main.db_service, "get_business_by_phone_id", fake_get_business_by_phone_id)
    monkeypatch.setattr(main.conversation_manager, "get_context", fake_get_context)
    monkeypatch.setattr(main.conversation_manager, "save_message", fake_save_message)
    monkeypatch.setattr(main.whatsapp_client, "send_text_message", fake_send_text_message)

    # Forzar ruta menú para no depender de OpenAI.
    monkeypatch.setattr(main, "classify_route", lambda _text: "menu")

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
    client = TestClient(main.app)
    resp = client.post("/webhooks/whatsapp", json=payload, headers={"X-Hub-Signature-256": "sha256=ok"})
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
