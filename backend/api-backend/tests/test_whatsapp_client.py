"""
whatsapp_client: envíos multi-tenant usan el phone_number_id del negocio;
sin él, fail-fast (placeholder/vacío → ValueError), fallback solo con id real (dev/test).
"""
import asyncio

from importlib import import_module

import pytest

whatsapp_client_module = import_module("app.services.whatsapp_client")
from app.services.whatsapp_client import whatsapp_client


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

    monkeypatch.setattr(whatsapp_client_module.httpx, "AsyncClient", FakeAsyncClient)
    return captured


def test_send_text_message_uses_tenant_phone_number_id(monkeypatch):
    captured = _capture_post(monkeypatch)

    asyncio.run(
        whatsapp_client.send_text_message("18095551234", "Hola", phone_number_id="987654321")
    )

    assert captured["url"].endswith("/987654321/messages")


def test_send_text_message_raises_with_placeholder_config(monkeypatch):
    monkeypatch.setattr(
        whatsapp_client_module.config, "META_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID"
    )

    with pytest.raises(ValueError):
        asyncio.run(whatsapp_client.send_text_message("18095551234", "Hola"))


def test_send_text_message_falls_back_to_dev_phone_number_id(monkeypatch):
    monkeypatch.setattr(whatsapp_client_module.config, "META_PHONE_NUMBER_ID", "555000111")
    captured = _capture_post(monkeypatch)

    asyncio.run(whatsapp_client.send_text_message("18095551234", "Hola"))

    assert captured["url"].endswith("/555000111/messages")


def test_send_interactive_buttons_uses_tenant_phone_number_id(monkeypatch):
    captured = _capture_post(monkeypatch)

    asyncio.run(
        whatsapp_client.send_interactive_buttons(
            "18095551234",
            "¿Confirmas?",
            [{"id": "yes", "title": "Sí"}],
            phone_number_id="987654321",
        )
    )

    assert captured["url"].endswith("/987654321/messages")
    assert captured["json"]["interactive"]["type"] == "button"


def test_send_interactive_buttons_raises_with_placeholder_config(monkeypatch):
    monkeypatch.setattr(
        whatsapp_client_module.config, "META_PHONE_NUMBER_ID", "YOUR_PHONE_NUMBER_ID"
    )

    with pytest.raises(ValueError):
        asyncio.run(
            whatsapp_client.send_interactive_buttons(
                "18095551234", "¿Confirmas?", [{"id": "yes", "title": "Sí"}]
            )
        )


def test_mark_as_read_uses_tenant_phone_number_id(monkeypatch):
    captured = _capture_post(monkeypatch)

    asyncio.run(whatsapp_client.mark_as_read("wamid.1", phone_number_id="987654321"))

    assert captured["url"].endswith("/987654321/messages")
    assert captured["json"]["status"] == "read"


def test_send_list_message_builds_exact_payload(monkeypatch):
    captured = _capture_post(monkeypatch)
    sections = [
        {
            "title": "Servicios",
            "rows": [
                {"id": "service_3", "title": "Corte de cabello"},
                {"id": "service_4", "title": "Barba"},
            ],
        }
    ]

    asyncio.run(
        whatsapp_client.send_list_message(
            "18095551234",
            "¿Qué servicio querés reservar?",
            sections,
            phone_number_id="987654321",
        )
    )

    payload = captured["json"]
    assert captured["url"].endswith("/987654321/messages")
    assert payload["to"] == "18095551234"
    assert payload["type"] == "interactive"
    assert payload["interactive"]["type"] == "list"
    assert payload["interactive"]["body"]["text"] == "¿Qué servicio querés reservar?"
    assert payload["interactive"]["action"]["button"] == "Ver opciones"
    assert payload["interactive"]["action"]["sections"] == sections


def test_send_list_message_rejects_over_ten_rows(monkeypatch):
    _capture_post(monkeypatch)
    sections = [
        {"title": "A", "rows": [{"id": f"row_{i}", "title": f"Opción {i}"} for i in range(6)]},
        {"title": "B", "rows": [{"id": f"row_{i}", "title": f"Opción {i}"} for i in range(5)]},
    ]

    with pytest.raises(ValueError):
        asyncio.run(
            whatsapp_client.send_list_message(
                "18095551234", "Demasiadas filas", sections, phone_number_id="987654321"
            )
        )


def test_send_list_message_rejects_empty_sections(monkeypatch):
    _capture_post(monkeypatch)

    with pytest.raises(ValueError):
        asyncio.run(
            whatsapp_client.send_list_message(
                "18095551234", "Sin secciones", [], phone_number_id="987654321"
            )
        )


def test_send_list_message_clips_long_titles_and_button(monkeypatch):
    captured = _capture_post(monkeypatch)
    sections = [
        {
            "title": "T" * 30,
            "rows": [{"id": "service_1", "title": "Corte de cabello con barba y arreglo" * 2}],
        }
    ]

    asyncio.run(
        whatsapp_client.send_list_message(
            "18095551234",
            "Body",
            sections,
            button_label="B" * 30,
            phone_number_id="987654321",
        )
    )

    action = captured["json"]["interactive"]["action"]
    assert len(action["button"]) <= 20
    assert len(action["sections"][0]["title"]) <= 24
    assert len(action["sections"][0]["rows"][0]["title"]) <= 24


def test_extract_list_reply_parses_id():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "987654321"},
                            "messages": [
                                {
                                    "id": "wamid.list",
                                    "from": "18095551234",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "list_reply",
                                        "list_reply": {
                                            "id": "slot_2026-08-30_09:00",
                                            "title": "9:00 AM",
                                        },
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    result = whatsapp_client.extract_message_from_webhook(payload)

    assert result is not None
    assert result["list_payload"] == "slot_2026-08-30_09:00"
    assert result["text"] == "9:00 AM"
    assert result["type"] == "interactive"


def test_send_template_message_builds_payload(monkeypatch):
    captured = _capture_post(monkeypatch)

    asyncio.run(
        whatsapp_client.send_template_message(
            "18095551234",
            "appointment_reminder",
            "es",
            ["Ana", "Corte", "30 de agosto", "9:00 AM", "Barbería", "Calle 1"],
            button_payloads={0: "reminder_ack_5", 1: "modify_appt_5", 2: "cancel_appt_5"},
            phone_number_id="987654321",
        )
    )

    payload = captured["json"]
    assert captured["url"].endswith("/987654321/messages")
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "appointment_reminder"
    assert payload["template"]["language"]["code"] == "es"
    body = next(c for c in payload["template"]["components"] if c["type"] == "body")
    assert body["parameters"] == [
        {"type": "text", "text": p}
        for p in ["Ana", "Corte", "30 de agosto", "9:00 AM", "Barbería", "Calle 1"]
    ]
    buttons = [c for c in payload["template"]["components"] if c["type"] == "button"]
    assert len(buttons) == 3
    assert buttons[0]["index"] == "0"
    assert buttons[0]["sub_type"] == "quick_reply"
    assert buttons[0]["parameters"] == [{"type": "payload", "payload": "reminder_ack_5"}]
    assert buttons[2]["parameters"] == [{"type": "payload", "payload": "cancel_appt_5"}]


def test_send_template_message_without_buttons_omits_button_components(monkeypatch):
    captured = _capture_post(monkeypatch)

    asyncio.run(
        whatsapp_client.send_template_message(
            "18095551234", "appointment_reminder", "es", ["Ana"], phone_number_id="987654321"
        )
    )

    types = [c["type"] for c in captured["json"]["template"]["components"]]
    assert types == ["body"]


def test_send_template_message_raises_api_error_with_code(monkeypatch):
    import httpx

    error_body = {"error": {"code": 131026, "message": "Plantilla no aprobada"}}

    class FakeResponse:
        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "400 Bad Request",
                request=httpx.Request("POST", "https://graph.facebook.com/v21.0/1/messages"),
                response=httpx.Response(400, json=error_body),
            )

        def json(self):
            return error_body

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(whatsapp_client_module.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(whatsapp_client_module.WhatsAppAPIError) as exc:
        asyncio.run(
            whatsapp_client.send_template_message(
                "18095551234",
                "appointment_reminder",
                "es",
                ["Ana"],
                phone_number_id="987654321",
            )
        )

    assert exc.value.code == 131026


def test_extract_status_update_parses():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "987654321"},
                            "statuses": [
                                {
                                    "id": "wamid.status1",
                                    "status": "failed",
                                    "recipient_id": "18095551234",
                                    "errors": [{"code": 131026, "title": "Plantilla no aprobada"}],
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    result = whatsapp_client.extract_message_from_webhook(payload)

    assert result is not None
    assert result["type"] == "status_update"
    assert result["status"] == "failed"
    assert result["message_id"] == "wamid.status1"
    assert result["recipient_id"] == "18095551234"
    assert result["errors"][0]["code"] == 131026
    assert result["business_phone_number_id"] == "987654321"


def test_extract_payload_without_messages_or_statuses_returns_none():
    payload = {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "1"}}}]}]}

    assert whatsapp_client.extract_message_from_webhook(payload) is None
