import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services import idempotency


@pytest.mark.asyncio
async def test_should_process_channel_event_accepts_new_db_event(monkeypatch):
    async def fake_record_event_db(**_kwargs):
        return True

    monkeypatch.setattr(idempotency, "_record_event_db", fake_record_event_db)

    assert await idempotency.should_process_channel_event(
        channel="whatsapp",
        business_id=1,
        user_key="w:1",
        event_id="evt-1",
    ) is True


@pytest.mark.asyncio
async def test_should_process_channel_event_rejects_db_duplicate(monkeypatch):
    async def fake_record_event_db(**_kwargs):
        return False

    monkeypatch.setattr(idempotency, "_record_event_db", fake_record_event_db)

    assert await idempotency.should_process_channel_event(
        channel="telegram",
        business_id=1,
        user_key="tg:1",
        event_id="evt-2",
    ) is False


@pytest.mark.asyncio
async def test_should_process_channel_event_uses_memory_fallback_when_db_unavailable(monkeypatch):
    idempotency._seen_events.clear()

    async def fake_record_event_db(**_kwargs):
        raise SQLAlchemyError("db down")

    monkeypatch.setattr(idempotency, "_record_event_db", fake_record_event_db)

    first = await idempotency.should_process_channel_event(
        channel="whatsapp",
        business_id=1,
        user_key="w:2",
        event_id="evt-3",
    )
    second = await idempotency.should_process_channel_event(
        channel="whatsapp",
        business_id=1,
        user_key="w:2",
        event_id="evt-3",
    )

    assert first is True
    assert second is False
