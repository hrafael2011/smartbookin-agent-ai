"""Lightweight channel-event idempotency guard for webhook retries."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.database import AsyncSessionLocal
from app.models import ProcessedChannelEvent

logger = logging.getLogger(__name__)

_seen_events: dict[str, float] = {}
_lock = asyncio.Lock()


def _event_key(
    channel: str,
    business_id: int,
    user_key: str,
    event_id: str,
) -> str:
    return f"{channel}:b{business_id}:u{user_key}:e{event_id}"


def _cleanup_expired(now: float) -> None:
    expired = [key for key, expires_at in _seen_events.items() if expires_at <= now]
    for key in expired[:500]:
        _seen_events.pop(key, None)


async def should_process_channel_event(
    *,
    channel: str,
    business_id: int,
    user_key: str,
    event_id: Optional[str],
    ttl_seconds: int = 6 * 60 * 60,
) -> bool:
    """Return False when the same channel event was already accepted recently."""
    if not event_id:
        return True

    try:
        return await _record_event_db(
            channel=channel,
            business_id=business_id,
            user_key=user_key,
            event_id=str(event_id),
        )
    except SQLAlchemyError as exc:
        logger.warning(
            "idempotency_db_unavailable channel=%s business=%s user=%s event=%s error=%s",
            channel,
            business_id,
            user_key,
            event_id,
            exc.__class__.__name__,
        )

    now = time.time()
    key = _event_key(channel, business_id, user_key, str(event_id))

    async with _lock:
        _cleanup_expired(now)
        if key in _seen_events:
            logger.info(
                "duplicate_event_ignored channel=%s business=%s user=%s event=%s",
                channel,
                business_id,
                user_key,
                event_id,
            )
            return False
        _seen_events[key] = now + ttl_seconds
        return True


async def _record_event_db(
    *,
    channel: str,
    business_id: int,
    user_key: str,
    event_id: str,
) -> bool:
    """Atomically record an event in PostgreSQL. Duplicate key means already seen."""
    async with AsyncSessionLocal() as db:
        db.add(
            ProcessedChannelEvent(
                channel=channel,
                business_id=business_id,
                user_key=user_key,
                event_id=event_id,
            )
        )
        try:
            await db.commit()
            return True
        except IntegrityError:
            await db.rollback()
            logger.info(
                "duplicate_event_ignored channel=%s business=%s user=%s event=%s",
                channel,
                business_id,
                user_key,
                event_id,
            )
            return False
