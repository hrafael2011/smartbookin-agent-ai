"""Refresh tokens opacos en BD: rotación en cada /auth/refresh y revocación en logout."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal
from app.models import Owner, RefreshToken

REFRESH_DAYS = 7
_PLAIN_BYTES = 48


def hash_refresh_plain(plain: str) -> str:
    return hashlib.sha256(plain.strip().encode("utf-8")).hexdigest()


async def issue_refresh_token(owner_id: int) -> str:
    plain = secrets.token_urlsafe(_PLAIN_BYTES)
    h = hash_refresh_plain(plain)
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS)
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RefreshToken).where(RefreshToken.owner_id == owner_id))
        db.add(RefreshToken(owner_id=owner_id, token_hash=h, expires_at=exp))
        await db.commit()
    return plain


async def revoke_all_refresh_tokens(owner_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(RefreshToken).where(RefreshToken.owner_id == owner_id))
        await db.commit()


async def consume_and_rotate_refresh(plain: str):
    if not plain or not plain.strip():
        return None, None
    h = hash_refresh_plain(plain)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == h))
        row = result.scalars().first()
        if not row:
            return None, None
        if row.expires_at < now:
            await db.delete(row)
            await db.commit()
            return None, None
        owner_id = row.owner_id
        await db.delete(row)
        await db.commit()

    new_plain = await issue_refresh_token(owner_id)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Owner).where(Owner.id == owner_id))
        owner = result.scalars().first()
    return owner, new_plain
