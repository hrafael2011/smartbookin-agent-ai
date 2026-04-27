"""Multi-tenant Telegram (un solo bot): enlaces por negocio y vínculo usuario↔negocio."""
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import Business, TelegramUserBinding


def tg_chat_key(chat_id: str) -> str:
    return f"tg:{chat_id}"


def generate_invite_token() -> str:
    # Límite Telegram /start payload: 64 caracteres
    return secrets.token_urlsafe(18).replace("+", "").replace("/", "")[:42]


async def ensure_invite_token(business_id: int) -> Optional[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.id == business_id))
        business = result.scalars().first()
        if not business:
            return None
        if not business.telegram_invite_token:
            business.telegram_invite_token = generate_invite_token()
            await db.commit()
            await db.refresh(business)
        return business.telegram_invite_token


async def resolve_invite_token(token: str) -> Optional[int]:
    if not token or len(token) < 8:
        return None
    token = token.strip()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business).filter(Business.telegram_invite_token == token)
        )
        business = result.scalars().first()
        return business.id if business else None


async def rotate_invite_token(business_id: int) -> Optional[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.id == business_id))
        business = result.scalars().first()
        if not business:
            return None
        business.telegram_invite_token = generate_invite_token()
        await db.commit()
        await db.refresh(business)
        return business.telegram_invite_token


async def get_binding_business_id(telegram_user_id: str) -> Optional[int]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TelegramUserBinding).filter(
                TelegramUserBinding.telegram_user_id == telegram_user_id
            )
        )
        row = result.scalars().first()
        return row.business_id if row else None


async def set_user_binding(telegram_user_id: str, business_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TelegramUserBinding).filter(
                TelegramUserBinding.telegram_user_id == telegram_user_id
            )
        )
        row = result.scalars().first()
        if row:
            row.business_id = business_id
            row.updated_at = datetime.now(timezone.utc)
        else:
            db.add(
                TelegramUserBinding(
                    telegram_user_id=telegram_user_id,
                    business_id=business_id,
                )
            )
        await db.commit()


async def clear_user_binding(telegram_user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TelegramUserBinding).filter(
                TelegramUserBinding.telegram_user_id == telegram_user_id
            )
        )
        row = result.scalars().first()
        if row:
            await db.delete(row)
            await db.commit()


async def mark_first_telegram_contact(business_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.id == business_id))
        business = result.scalars().first()
        if business and business.telegram_first_contact_at is None:
            business.telegram_first_contact_at = datetime.now(timezone.utc)
            await db.commit()


async def get_telegram_activation_snapshot(business_id: int) -> Optional[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.id == business_id))
        business = result.scalars().first()
        if not business:
            return None
        if not business.telegram_invite_token:
            business.telegram_invite_token = generate_invite_token()
            await db.commit()
            await db.refresh(business)
        token = business.telegram_invite_token
        return {
            "invite_token": token,
            "has_first_contact": business.telegram_first_contact_at is not None,
            "first_contact_at": business.telegram_first_contact_at,
        }
