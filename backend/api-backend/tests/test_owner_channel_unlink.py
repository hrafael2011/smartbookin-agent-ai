"""Real DB-backed tests for owner/customer Telegram unlink paths.

The suite has no external DB fixtures, so these tests run the real service
functions and endpoints against an in-memory SQLite database (stdlib driver,
no extra dependencies) through a thin async facade over a sync Session.
The services under test are NOT monkeypatched: only the AsyncSessionLocal
factory is swapped so their sessions hit the in-memory DB.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, types
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import businesses as businesses_api
from app.core.database import Base
from app.models import Business, OwnerChannelBinding, TelegramUserBinding
from app.schemas import TelegramUnlinkOut
from app.services import owner_channel_service as owner_service
from app.services import telegram_link_service as link_service


class _UtcDateTime(types.TypeDecorator):
    """Store naive UTC in SQLite, but read back timezone-aware datetimes.

    SQLite does not support timezone-aware columns; without this the real
    expiry comparison in ``activate_owner_telegram_binding`` would compare
    naive vs aware datetimes. Postgres (the production dialect) always
    returns aware datetimes, so this mirrors production semantics.
    """

    impl = types.DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


# Only DB-backed tests read this column; the override is scoped to this file.
OwnerChannelBinding.__table__.c.activation_expires_at.type = _UtcDateTime()


class _AsyncSessionFacade:
    """Async-session-shaped wrapper over a sync SQLAlchemy Session."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        self._session.close()
        return False

    async def execute(self, statement):
        return self._session.execute(statement)

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()

    async def refresh(self, obj):
        self._session.refresh(obj)

    def add(self, obj):
        self._session.add(obj)

    def delete(self, obj):
        self._session.delete(obj)


class _Owner:
    id = 7


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(db_engine, monkeypatch):
    """Patches AsyncSessionLocal in both services to use the in-memory DB."""

    def factory():
        return _AsyncSessionFacade(Session(db_engine))

    monkeypatch.setattr(owner_service, "AsyncSessionLocal", factory)
    monkeypatch.setattr(link_service, "AsyncSessionLocal", factory)
    return factory


async def _seed_business_and_binding(
    session_factory,
    *,
    business_id: int = 1,
    owner_id: int = _Owner.id,
    token: str = "oldtok",
    tg_user: str = "tg1",
    is_active: bool = True,
):
    async with session_factory() as db:
        db.add(
            Business(
                id=business_id,
                owner_id=owner_id,
                name="Demo",
                phone_number=f"809000000{business_id}",
            )
        )
        db.add(
            OwnerChannelBinding(
                owner_id=owner_id,
                business_id=business_id,
                channel="telegram",
                role="owner",
                is_active=is_active,
                channel_user_id=tg_user,
                activation_token=token,
                activation_expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
            )
        )
        await db.commit()


async def _get_binding(session_factory, business_id: int = 1) -> OwnerChannelBinding:
    async with session_factory() as db:
        return (
            await db.execute(
                select(OwnerChannelBinding).filter(
                    OwnerChannelBinding.business_id == business_id
                )
            )
        ).scalars().first()


@pytest.mark.asyncio
async def test_deactivate_owner_telegram_binding_revokes_token(session_factory):
    await _seed_business_and_binding(session_factory, token="revoketok")

    ok = await owner_service.deactivate_owner_telegram_binding(
        owner_id=_Owner.id,
        business_id=1,
    )

    assert ok is True
    binding = await _get_binding(session_factory)
    assert binding.is_active is False
    assert binding.channel_user_id is None
    assert binding.activation_token is None
    assert binding.activation_expires_at is None


@pytest.mark.asyncio
async def test_deactivate_owner_telegram_binding_not_found_returns_false(session_factory):
    ok = await owner_service.deactivate_owner_telegram_binding(
        owner_id=_Owner.id,
        business_id=1,
    )
    assert ok is False


@pytest.mark.asyncio
async def test_deactivate_owner_telegram_bindings_by_user_revokes_token(session_factory):
    # (channel, channel_user_id) is unique, so one binding per user; a second
    # binding for a different user must remain untouched.
    await _seed_business_and_binding(session_factory, business_id=1, token="tok1", tg_user="tg1")
    await _seed_business_and_binding(session_factory, business_id=2, token="tok2", tg_user="tg2")

    count = await owner_service.deactivate_owner_telegram_bindings_by_user("tg1")

    assert count == 1
    binding1 = await _get_binding(session_factory, business_id=1)
    assert binding1.is_active is False
    assert binding1.channel_user_id is None
    assert binding1.activation_token is None
    assert binding1.activation_expires_at is None

    binding2 = await _get_binding(session_factory, business_id=2)
    assert binding2.is_active is True
    assert binding2.activation_token == "tok2"
    assert binding2.activation_expires_at is not None


@pytest.mark.asyncio
async def test_clear_business_telegram_bindings_removes_rows_and_resets_first_contact(session_factory):
    async with session_factory() as db:
        db.add(
            Business(
                id=1,
                owner_id=_Owner.id,
                name="Demo",
                phone_number="8090000001",
                telegram_first_contact_at=datetime.now(timezone.utc),
            )
        )
        db.add(TelegramUserBinding(telegram_user_id="c1", business_id=1))
        db.add(TelegramUserBinding(telegram_user_id="c2", business_id=1))
        await db.commit()

    count = await link_service.clear_business_telegram_bindings(1)

    assert count == 2
    async with session_factory() as db:
        remaining = (
            await db.execute(
                select(func.count(TelegramUserBinding.id)).filter(
                    TelegramUserBinding.business_id == 1
                )
            )
        ).scalar_one()
        assert remaining == 0
        business = (
            await db.execute(select(Business).filter(Business.id == 1))
        ).scalars().first()
        assert business.telegram_first_contact_at is None


@pytest.mark.asyncio
async def test_reactivate_with_old_token_fails_after_deactivation(session_factory):
    await _seed_business_and_binding(session_factory, token="stale_token")

    await owner_service.deactivate_owner_telegram_binding(
        owner_id=_Owner.id,
        business_id=1,
    )

    result = await owner_service.activate_owner_telegram_binding(
        payload="owner_stale_token",
        telegram_user_id="tg1",
    )
    assert result["status"] == "invalid"


@pytest.mark.asyncio
async def test_activate_with_fresh_token_still_works(session_factory):
    await _seed_business_and_binding(session_factory, token="fresh_token")

    result = await owner_service.activate_owner_telegram_binding(
        payload="owner_fresh_token",
        telegram_user_id="tg1",
    )

    assert result["status"] == "ok"
    binding = await _get_binding(session_factory)
    assert binding.is_active is True
    assert binding.channel_user_id == "tg1"


@pytest.mark.asyncio
async def test_unlink_owner_telegram_endpoint_deactivates_binding(session_factory):
    await _seed_business_and_binding(session_factory, token="endpoint_tok")

    result = await businesses_api.unlink_owner_telegram(
        1,
        db=(await session_factory().__aenter__()),
        current_owner=_Owner(),
    )

    assert result is None
    binding = await _get_binding(session_factory)
    assert binding.is_active is False
    assert binding.activation_token is None
    assert binding.activation_expires_at is None


@pytest.mark.asyncio
async def test_unlink_owner_telegram_endpoint_404_for_unowned_business(session_factory):
    await _seed_business_and_binding(
        session_factory,
        business_id=1,
        owner_id=99,
        token="other_tok",
    )

    with pytest.raises(HTTPException) as exc:
        await businesses_api.unlink_owner_telegram(
            1,
            db=(await session_factory().__aenter__()),
            current_owner=_Owner(),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unlink_customer_telegram_bindings_endpoint_returns_count(session_factory):
    async with session_factory() as db:
        db.add(
            Business(
                id=1,
                owner_id=_Owner.id,
                name="Demo",
                phone_number="8090000001",
                telegram_first_contact_at=datetime.now(timezone.utc),
            )
        )
        db.add(TelegramUserBinding(telegram_user_id="c1", business_id=1))
        db.add(TelegramUserBinding(telegram_user_id="c2", business_id=1))
        await db.commit()

    out = await businesses_api.unlink_customer_telegram_bindings(
        1,
        db=(await session_factory().__aenter__()),
        current_owner=_Owner(),
    )

    assert isinstance(out, TelegramUnlinkOut)
    assert out.unlinked_count == 2
    async with session_factory() as db:
        remaining = (
            await db.execute(
                select(func.count(TelegramUserBinding.id)).filter(
                    TelegramUserBinding.business_id == 1
                )
            )
        ).scalar_one()
        assert remaining == 0


@pytest.mark.asyncio
async def test_unlink_customer_telegram_bindings_endpoint_404_for_unowned_business(session_factory):
    async with session_factory() as db:
        db.add(
            Business(
                id=1,
                owner_id=99,
                name="Demo",
                phone_number="8090000001",
            )
        )
        db.add(TelegramUserBinding(telegram_user_id="c1", business_id=1))
        await db.commit()

    with pytest.raises(HTTPException) as exc:
        await businesses_api.unlink_customer_telegram_bindings(
            1,
            db=(await session_factory().__aenter__()),
            current_owner=_Owner(),
        )

    assert exc.value.status_code == 404
