"""Owner-only Telegram channel activation and binding helpers."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models import Business, OwnerChannelBinding

OWNER_TELEGRAM_PREFIX = "owner_"
OWNER_ACTIVATION_TTL_HOURS = 48


def generate_owner_activation_token() -> str:
    # Telegram /start payload max is 64 chars; prefix is added outside this token.
    return secrets.token_urlsafe(18).replace("+", "").replace("/", "")[:42]


def owner_start_payload(token: str) -> str:
    return f"{OWNER_TELEGRAM_PREFIX}{token}"


def is_owner_start_payload(payload: str) -> bool:
    return str(payload or "").strip().startswith(OWNER_TELEGRAM_PREFIX)


def strip_owner_start_payload(payload: str) -> str:
    raw = str(payload or "").strip()
    return raw[len(OWNER_TELEGRAM_PREFIX) :] if is_owner_start_payload(raw) else raw


async def get_owned_business_count(owner_id: int) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business.id).filter(Business.owner_id == owner_id))
        return len(result.scalars().all())


async def get_owner_telegram_activation_snapshot(
    *,
    owner_id: int,
    business_id: int,
) -> Optional[dict]:
    """Create or rotate a pending owner Telegram activation token."""
    async with AsyncSessionLocal() as db:
        businesses = (
            await db.execute(select(Business).filter(Business.owner_id == owner_id))
        ).scalars().all()
        if len(businesses) != 1:
            return {"status": "requires_support", "business_count": len(businesses)}
        business = businesses[0]
        if business.id != business_id:
            return None

        result = await db.execute(
            select(OwnerChannelBinding).filter(
                OwnerChannelBinding.owner_id == owner_id,
                OwnerChannelBinding.business_id == business_id,
                OwnerChannelBinding.channel == "telegram",
            )
        )
        binding = result.scalars().first()
        token = generate_owner_activation_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=OWNER_ACTIVATION_TTL_HOURS)

        if binding:
            binding.activation_token = token
            binding.activation_expires_at = expires_at
        else:
            binding = OwnerChannelBinding(
                owner_id=owner_id,
                business_id=business_id,
                channel="telegram",
                role="owner",
                is_active=False,
                activation_token=token,
                activation_expires_at=expires_at,
            )
            db.add(binding)

        await db.commit()
        await db.refresh(binding)

        return {
            "status": "ok",
            "activation_token": token,
            "payload": owner_start_payload(token),
            "activation_expires_at": expires_at,
            "has_active_binding": bool(binding.is_active and binding.channel_user_id),
            "business_name": business.name,
        }


async def activate_owner_telegram_binding(
    *,
    payload: str,
    telegram_user_id: str,
) -> dict:
    """Activate an owner binding from `/start owner_<token>`."""
    token = strip_owner_start_payload(payload)
    if not token:
        return {"status": "invalid"}

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OwnerChannelBinding, Business)
            .join(Business, OwnerChannelBinding.business_id == Business.id)
            .filter(
                OwnerChannelBinding.activation_token == token,
                OwnerChannelBinding.channel == "telegram",
            )
        )
        row = result.first()
        if not row:
            return {"status": "invalid"}

        binding, business = row
        if binding.activation_expires_at and binding.activation_expires_at < now:
            return {"status": "expired"}

        existing_result = await db.execute(
            select(OwnerChannelBinding).filter(
                OwnerChannelBinding.channel == "telegram",
                OwnerChannelBinding.channel_user_id == str(telegram_user_id),
                OwnerChannelBinding.id != binding.id,
            )
        )
        if existing_result.scalars().first():
            return {"status": "channel_user_conflict"}

        binding.channel_user_id = str(telegram_user_id)
        binding.is_active = True
        binding.activated_at = binding.activated_at or now
        binding.last_used_at = now

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return {"status": "channel_user_conflict"}

        return {
            "status": "ok",
            "owner_id": binding.owner_id,
            "business_id": binding.business_id,
            "business_name": business.name,
        }


async def get_owner_binding_by_telegram_user_id(telegram_user_id: str) -> Optional[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OwnerChannelBinding, Business)
            .join(Business, OwnerChannelBinding.business_id == Business.id)
            .filter(
                OwnerChannelBinding.channel == "telegram",
                OwnerChannelBinding.channel_user_id == str(telegram_user_id),
                OwnerChannelBinding.is_active == True,
            )
        )
        row = result.first()
        if not row:
            return None
        binding, business = row
        binding.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        return {
            "owner_id": binding.owner_id,
            "business_id": binding.business_id,
            "business_name": business.name,
            "role": binding.role,
        }
