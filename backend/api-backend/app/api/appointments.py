from typing import List
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_owner
from app.models import Appointment, Business, Owner
from app.schemas import AppointmentCreate, AppointmentOut

router = APIRouter()


def _normalize_status(value: str) -> str:
    status_map = {
        "pending": "P",
        "confirmed": "C",
        "cancelled": "A",
        "canceled": "A",
        "completed": "D",
        "P": "P",
        "C": "C",
        "A": "A",
        "D": "D",
    }
    return status_map.get(value, value)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    if len(value) == 10:
        return datetime.fromisoformat(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.post("/{business_id}/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(business_id: int, appointment_in: AppointmentCreate, db: AsyncSession = Depends(get_db)):
    # Anyone can create an appointment
    new_appointment = Appointment(**appointment_in.model_dump(), business_id=business_id)
    db.add(new_appointment)
    await db.commit()
    await db.refresh(new_appointment)
    return new_appointment

@router.get("/{business_id}/appointments", response_model=List[AppointmentOut])
async def get_appointments(
    business_id: int,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    # Protect with auth
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    query = select(Appointment).filter(Appointment.business_id == business_id)

    dt_from = _parse_datetime(date_from)
    if dt_from:
        query = query.filter(Appointment.date >= dt_from)

    dt_to = _parse_datetime(date_to)
    if dt_to:
        if len(date_to or "") == 10:
            dt_to = dt_to.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.filter(Appointment.date <= dt_to)

    if status_filter:
        query = query.filter(Appointment.status == _normalize_status(status_filter))

    result = await db.execute(query.order_by(Appointment.date.asc()))
    return result.scalars().all()


@router.get("/{business_id}/appointments/{appointment_id}", response_model=AppointmentOut)
async def get_appointment(
    business_id: int,
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Appointment).filter(
            Appointment.id == appointment_id, Appointment.business_id == business_id
        )
    )
    appointment = result.scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment


@router.patch("/{business_id}/appointments/{appointment_id}", response_model=AppointmentOut)
async def update_appointment(
    business_id: int,
    appointment_id: int,
    appointment_in: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Appointment).filter(
            Appointment.id == appointment_id, Appointment.business_id == business_id
        )
    )
    appointment = result.scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if "scheduled_at" in appointment_in:
        appointment.date = _parse_datetime(appointment_in["scheduled_at"]) or appointment.date
    if "date" in appointment_in:
        appointment.date = _parse_datetime(appointment_in["date"]) or appointment.date
    if "status" in appointment_in:
        appointment.status = _normalize_status(str(appointment_in["status"]))
    if "customer_id" in appointment_in:
        appointment.customer_id = int(appointment_in["customer_id"])
    if "service_id" in appointment_in:
        appointment.service_id = int(appointment_in["service_id"])

    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.post("/{business_id}/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
async def cancel_appointment(
    business_id: int,
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Appointment).filter(
            Appointment.id == appointment_id, Appointment.business_id == business_id
        )
    )
    appointment = result.scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = "A"
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.delete("/{business_id}/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    business_id: int,
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    current_owner: Owner = Depends(get_current_owner),
):
    result = await db.execute(select(Business).filter(Business.id == business_id, Business.owner_id == current_owner.id))
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Business not found or unauthorized")

    result = await db.execute(
        select(Appointment).filter(
            Appointment.id == appointment_id, Appointment.business_id == business_id
        )
    )
    appointment = result.scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    await db.delete(appointment)
    await db.commit()
    return None
