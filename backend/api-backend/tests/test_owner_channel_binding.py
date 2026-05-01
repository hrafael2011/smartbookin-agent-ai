from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api import businesses as businesses_api
from app.models import Business
from app.services import owner_channel_service as owner_service
from app.services import telegram_inbound


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _ExecuteResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _ScalarResult(self.value)


class _FakeDb:
    def __init__(self, value):
        self.value = value

    async def execute(self, *_args, **_kwargs):
        return _ExecuteResult(self.value)


class _Owner:
    id = 7


def test_owner_start_payload_helpers():
    token = owner_service.generate_owner_activation_token()
    payload = owner_service.owner_start_payload(token)

    assert 8 <= len(token) <= 64
    assert owner_service.is_owner_start_payload(payload) is True
    assert owner_service.strip_owner_start_payload(payload) == token
    assert owner_service.is_owner_start_payload(token) is False


@pytest.mark.asyncio
async def test_owner_telegram_activation_endpoint_returns_prefixed_payload(monkeypatch):
    business = Business(id=3, owner_id=_Owner.id, name="Demo", phone_number="8090000000")

    async def fake_snapshot(*_args, **_kwargs):
        return {
            "status": "ok",
            "activation_token": "abc123owner",
            "payload": "owner_abc123owner",
            "activation_expires_at": datetime.now(timezone.utc),
            "has_active_binding": False,
        }

    monkeypatch.setattr(businesses_api.config, "TELEGRAM_BOT_USERNAME", "SmartBookingBot")
    monkeypatch.setattr(
        businesses_api,
        "get_owner_telegram_activation_snapshot",
        fake_snapshot,
    )

    out = await businesses_api.get_owner_telegram_activation(
        3,
        db=_FakeDb(business),
        current_owner=_Owner(),
    )

    assert out.payload == "owner_abc123owner"
    assert out.deep_link.endswith("?start=owner_abc123owner")
    assert out.has_active_binding is False


@pytest.mark.asyncio
async def test_owner_telegram_activation_rejects_multiple_inherited_businesses(monkeypatch):
    business = Business(id=3, owner_id=_Owner.id, name="Demo", phone_number="8090000000")

    async def fake_snapshot(*_args, **_kwargs):
        return {"status": "requires_support", "business_count": 2}

    monkeypatch.setattr(
        businesses_api,
        "get_owner_telegram_activation_snapshot",
        fake_snapshot,
    )

    with pytest.raises(HTTPException) as exc:
        await businesses_api.get_owner_telegram_activation(
            3,
            db=_FakeDb(business),
            current_owner=_Owner(),
        )

    assert exc.value.status_code == 409
    assert "múltiples negocios heredados" in exc.value.detail


@pytest.mark.asyncio
async def test_telegram_owner_start_routes_before_customer_invite(monkeypatch):
    sent = []

    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {"from": "123", "text": "/start owner_TOKEN"},
    )

    async def fake_activate(**_kwargs):
        return {"status": "ok", "business_name": "Demo"}

    async def fail_customer_invite(_token):
        raise AssertionError("owner_ payload must not be resolved as customer invite")

    async def fake_send_text_message(*_args, **kwargs):
        sent.append(kwargs.get("message") or "")
        return {"ok": True}

    monkeypatch.setattr(telegram_inbound, "activate_owner_telegram_binding", fake_activate)
    monkeypatch.setattr(telegram_inbound, "resolve_invite_token", fail_customer_invite)
    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "send_text_message",
        fake_send_text_message,
    )

    resp = await telegram_inbound.process_telegram_update({})

    assert resp.get("status") == "ok"
    assert "Panel rápido" in sent[-1]


@pytest.mark.asyncio
async def test_telegram_customer_start_still_uses_customer_invite(monkeypatch):
    calls = {"customer_resolved": False, "owner_activated": False, "welcome": False}

    monkeypatch.setattr(
        telegram_inbound.telegram_client,
        "extract_message_from_webhook",
        lambda _payload: {"from": "123", "text": "/start CUSTOMER_TOKEN"},
    )

    async def fake_activate(**_kwargs):
        calls["owner_activated"] = True
        return {"status": "ok"}

    async def fake_resolve(_token):
        calls["customer_resolved"] = True
        return 9

    async def fake_set_binding(*_args, **_kwargs):
        return None

    async def fake_mark_first(*_args, **_kwargs):
        return None

    async def fake_welcome(*_args, **_kwargs):
        calls["welcome"] = True
        return None

    monkeypatch.setattr(telegram_inbound, "activate_owner_telegram_binding", fake_activate)
    monkeypatch.setattr(telegram_inbound, "resolve_invite_token", fake_resolve)
    monkeypatch.setattr(telegram_inbound, "set_user_binding", fake_set_binding)
    monkeypatch.setattr(telegram_inbound, "mark_first_telegram_contact", fake_mark_first)
    monkeypatch.setattr(telegram_inbound, "_send_welcome_for_business", fake_welcome)

    resp = await telegram_inbound.process_telegram_update({})

    assert resp.get("status") == "ok"
    assert calls == {
        "customer_resolved": True,
        "owner_activated": False,
        "welcome": True,
    }
