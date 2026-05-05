from typing import List
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_owner
from app.models import Service, Business, Owner
from app.schemas import ServiceCreate, ServiceOut

router = APIRouter()


def _validate_service_timing(
    data: dict,
    current_duration: int | None = None,
    current_buffer: int | None = None,
) -> None:
    duration = data.get("duration_minutes", current_duration)
    buffer_minutes = data.get("buffer_minutes", current_buffer if current_buffer is not None else 0)

    if duration is not None:
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="duration_minutes must be an integer")
        if duration <= 0:
            raise HTTPException(status_code=400, detail="duration_minutes must be greater than 0")

    try:
        buffer_minutes = int(buffer_minutes or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="buffer_minutes must be an integer")
    if buffer_minutes < 0 or buffer_minutes > 120:
        raise HTTPException(status_code=400, detail="buffer_minutes must be between 0 and 120")
    if duration is not None and duration + buffer_minutes > 480:
        raise HTTPException(
            status_code=400,
            detail="duration_minutes + buffer_minutes must not exceed 480",
        )


@router.post("/{business_id}/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
async def create_service(business_id: int, service_in: ServiceCreate, db: AsyncSession = Depends(get_db), current_owner: Owner = Depends(get_current_owner)):
    # Verify business belongs to owner
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")
        
    data = service_in.model_dump()
    _validate_service_timing(data)
    new_service = Service(**data, business_id=business_id)
    db.add(new_service)
    await db.commit()
    await db.refresh(new_service)
    return new_service

@router.get("/{business_id}/services", response_model=List[ServiceOut])
async def get_services(business_id: int, db: AsyncSession = Depends(get_db)):
    # Public endpoint to get services for a business
    result = await db.execute(select(Service).filter(Service.business_id == business_id))
    return result.scalars().all()


@router.get("/{business_id}/services/{service_id}", response_model=ServiceOut)
async def get_service(
    business_id: int,
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(
            Business.id == business_id, Business.owner_id == current_owner.id
        )
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Service).filter(Service.id == service_id, Service.business_id == business_id)
    )
    service = result.scalars().first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.patch("/{business_id}/services/{service_id}", response_model=ServiceOut)
async def update_service(
    business_id: int,
    service_id: int,
    service_in: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(
            Business.id == business_id, Business.owner_id == current_owner.id
        )
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Service).filter(Service.id == service_id, Service.business_id == business_id)
    )
    service = result.scalars().first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    _validate_service_timing(
        service_in,
        current_duration=service.duration_minutes,
        current_buffer=getattr(service, "buffer_minutes", 0) or 0,
    )
    allowed_fields = {"name", "description", "duration_minutes", "price", "is_active", "buffer_minutes"}
    for key, value in service_in.items():
        if key in allowed_fields:
            setattr(service, key, value)

    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/{business_id}/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    business_id: int,
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(
        select(Business).filter(
            Business.id == business_id, Business.owner_id == current_owner.id
        )
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Service).filter(Service.id == service_id, Service.business_id == business_id)
    )
    service = result.scalars().first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    await db.delete(service)
    await db.commit()
    return None
