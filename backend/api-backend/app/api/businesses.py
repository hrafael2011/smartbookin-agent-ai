from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import config
from app.core.database import get_db
from app.core.dependencies import get_current_owner
from app.models import Business, Owner
from app.schemas import (
    BusinessCreate,
    BusinessOut,
    BusinessUpdate,
    OwnerTelegramActivationOut,
    TelegramActivationOut,
)
from app.services.owner_channel_service import get_owner_telegram_activation_snapshot
from app.services.telegram_link_service import get_telegram_activation_snapshot, rotate_invite_token

router = APIRouter()

@router.post("/", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
async def create_business(business_in: BusinessCreate, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    result = await db.execute(
        select(Business.id).filter(Business.owner_id == current_owner.id).limit(1)
    )
    if result.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El MVP permite un negocio por dueño. "
                "Multi-negocio estará disponible en planes de pago."
            ),
        )

    new_business = Business(**business_in.model_dump(), owner_id=current_owner.id)
    db.add(new_business)
    await db.commit()
    await db.refresh(new_business)
    return new_business

@router.patch("/{business_id}", response_model=BusinessOut)
async def update_business(business_id: int, business_in: BusinessUpdate, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
        
    update_data = business_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(business, key, value)
    
    await db.commit()
    await db.refresh(business)
    return business

@router.get("/", response_model=List[BusinessOut])
async def get_businesses(db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    result = await db.execute(select(Business).filter(Business.owner_id == current_owner.id))
    return result.scalars().all()

@router.get("/{business_id}", response_model=BusinessOut)
async def get_business(business_id: int, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.get("/{business_id}/telegram", response_model=TelegramActivationOut)
async def get_telegram_activation(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    snap = await get_telegram_activation_snapshot(business_id)
    if not snap or not snap.get("invite_token"):
        raise HTTPException(status_code=500, detail="No se pudo generar el enlace de Telegram")

    token = snap["invite_token"]
    bot = config.TELEGRAM_BOT_USERNAME or ""
    deep = f"https://t.me/{bot}?start={token}" if bot else ""

    return TelegramActivationOut(
        deep_link=deep,
        invite_token=token,
        bot_username=bot,
        has_first_contact=bool(snap.get("has_first_contact")),
    )


@router.get("/{business_id}/owner-telegram", response_model=OwnerTelegramActivationOut)
async def get_owner_telegram_activation(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    snap = await get_owner_telegram_activation_snapshot(
        owner_id=current_owner.id,
        business_id=business_id,
    )
    if not snap:
        raise HTTPException(status_code=404, detail="Business not found")
    if snap.get("status") == "requires_support":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Tu cuenta tiene múltiples negocios heredados. "
                "Contacta soporte para resolver el negocio activo antes de activar el canal del dueño."
            ),
        )
    if snap.get("status") != "ok":
        raise HTTPException(status_code=500, detail="No se pudo generar el enlace del dueño")

    bot = config.TELEGRAM_BOT_USERNAME or ""
    payload = snap["payload"]
    deep = f"https://t.me/{bot}?start={payload}" if bot else ""

    return OwnerTelegramActivationOut(
        deep_link=deep,
        activation_token=snap["activation_token"],
        payload=payload,
        bot_username=bot,
        has_active_binding=bool(snap.get("has_active_binding")),
        activation_expires_at=snap["activation_expires_at"],
    )


@router.post("/{business_id}/telegram/rotate-invite", response_model=TelegramActivationOut)
async def rotate_telegram_invite(
    business_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id)
    )
    business = result.scalars().first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    new_token = await rotate_invite_token(business_id)
    if not new_token:
        raise HTTPException(status_code=500, detail="No se pudo rotar el token")

    snap = await get_telegram_activation_snapshot(business_id)
    bot = config.TELEGRAM_BOT_USERNAME or ""
    deep = f"https://t.me/{bot}?start={new_token}" if bot else ""

    return TelegramActivationOut(
        deep_link=deep,
        invite_token=new_token,
        bot_username=bot,
        has_first_contact=bool(snap and snap.get("has_first_contact")),
    )
