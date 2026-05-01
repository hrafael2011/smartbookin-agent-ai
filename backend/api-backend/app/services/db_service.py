from typing import Dict, List, Optional
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone
from sqlalchemy.future import select

from app.core.database import AsyncSessionLocal
from app.models import (
    Appointment,
    Business,
    Customer,
    ScheduleException,
    ScheduleRule,
    Service,
    TimeBlock,
)
from app.services.schedule_logic import apply_schedule_exceptions, build_slots

async def get_customer_by_channel(business_id: int, phone: str) -> Optional[Dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer).filter(Customer.business_id == business_id, Customer.phone_number == phone)
        )
        customer = result.scalars().first()
        if not customer:
            return None
        return {
            "id": customer.id,
            "name": customer.name,
            "phone_number": customer.phone_number,
        }


async def find_or_create_customer(business_id: int, phone: str, name: str) -> Dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Customer).filter(Customer.business_id == business_id, Customer.phone_number == phone)
        )
        customer = result.scalars().first()

        if not customer:
            customer = Customer(business_id=business_id, phone_number=phone, name=name)
            db.add(customer)
            await db.commit()
            await db.refresh(customer)
        else:
            # Completar nombre si antes estaba vacío (ej. primer contacto Telegram)
            if name and str(name).strip() and (
                not customer.name or not str(customer.name).strip()
            ):
                customer.name = str(name).strip()
                await db.commit()
                await db.refresh(customer)

        return {"customer": {"id": customer.id, "name": customer.name, "phone": customer.phone_number}}

async def get_business_services(business_id: int) -> List[Dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Service).filter(Service.business_id == business_id, Service.is_active == True))
        services = result.scalars().all()
        return [{"id": s.id, "name": s.name, "price": s.price, "duration_minutes": s.duration_minutes} for s in services]

async def get_business(business_id: int) -> Dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.id == business_id))
        business = result.scalars().first()
        if not business:
            return {}
        return {
            "id": business.id,
            "name": business.name,
            "address": business.address,
            "description": business.description,
            "timezone": business.timezone or "America/Santo_Domingo",
        }

async def get_business_by_phone_id(phone_id: str) -> Dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.whatsapp_phone_number_id == phone_id))
        business = result.scalars().first()
        if not business:
            return {}
        return {"id": business.id, "name": business.name, "address": business.address}


def _parse_target_date(date_value: str) -> date_type:
    try:
        if len(date_value) == 10:
            return date_type.fromisoformat(date_value)
        return datetime.fromisoformat(date_value.replace("Z", "+00:00")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _schedule_day_from_date(value: date_type) -> int:
    # Python weekday: Monday=0 ... Sunday=6
    # UI/API weekday: Sunday=0 ... Saturday=6
    return (value.weekday() + 1) % 7


def _utc_datetime(day: date_type, value: time) -> datetime:
    return datetime.combine(day, value).replace(tzinfo=timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def get_availability(business_id: int, service_id: int, date: str, preferred_time: Optional[str] = None) -> Dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Service).filter(
                Service.id == service_id,
                Service.business_id == business_id,
                Service.is_active == True,
            )
        )
        service = result.scalars().first()
        if not service:
            return {"available_slots": []}

        target_date = _parse_target_date(date)
        day_start = _utc_datetime(target_date, time(0, 0))
        day_end = _utc_datetime(target_date, time(23, 59, 59))

        schedule_day = _schedule_day_from_date(target_date)
        result = await db.execute(
            select(ScheduleRule)
            .filter(
                ScheduleRule.business_id == business_id,
                ScheduleRule.day_of_week == schedule_day,
            )
            .order_by(ScheduleRule.start_time.asc())
        )
        day_rules = result.scalars().all()

        if day_rules:
            base_ranges = [
                (rule.start_time, rule.end_time)
                for rule in day_rules
                if rule.is_available and rule.start_time < rule.end_time
            ]
        else:
            base_ranges = [(time(9, 0), time(18, 0))]

        result = await db.execute(
            select(ScheduleException).filter(
                ScheduleException.business_id == business_id,
                ScheduleException.date == target_date,
                ScheduleException.deleted_at.is_(None),
            )
        )
        day_exceptions = result.scalars().all()
        open_time_ranges = apply_schedule_exceptions(
            base_ranges,
            [
                {
                    "type": item.type,
                    "all_day": item.all_day,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                }
                for item in day_exceptions
            ],
        )

        if not open_time_ranges:
            return {"available_slots": []}

        open_datetime_ranges = [
            (_utc_datetime(target_date, start), _utc_datetime(target_date, end))
            for start, end in open_time_ranges
        ]

        blocked_datetime_ranges = []

        result = await db.execute(
            select(Appointment, Service.duration_minutes)
            .join(Service, Appointment.service_id == Service.id)
            .filter(
                Appointment.business_id == business_id,
                Appointment.status.in_(["P", "C"]),
                Appointment.date >= day_start,
                Appointment.date <= day_end,
            )
        )
        for appointment, duration_minutes in result.all():
            start_at = _as_utc(appointment.date)
            end_at = start_at + timedelta(minutes=int(duration_minutes))
            blocked_datetime_ranges.append((start_at, end_at))

        result = await db.execute(
            select(TimeBlock).filter(
                TimeBlock.business_id == business_id,
                TimeBlock.start_at < day_end,
                TimeBlock.end_at > day_start,
            )
        )
        for block in result.scalars().all():
            block_start = max(_as_utc(block.start_at), day_start)
            block_end = min(_as_utc(block.end_at), day_end)
            if block_start < block_end:
                blocked_datetime_ranges.append((block_start, block_end))

        slots = build_slots(
            open_ranges=open_datetime_ranges,
            blocked_ranges=blocked_datetime_ranges,
            duration_minutes=service.duration_minutes,
            preferred_time=preferred_time,
        )
        return {"available_slots": slots}

async def create_appointment(appointment_data: Dict) -> Dict:
    async with AsyncSessionLocal() as db:
        start_at = datetime.fromisoformat(appointment_data["start_at"].replace('Z', '+00:00'))
        
        appointment = Appointment(
            business_id=appointment_data["business"],
            customer_id=appointment_data["customer"],
            service_id=appointment_data["service"],
            date=start_at,
            status="C"
        )
        db.add(appointment)
        await db.commit()
        
        return {"id": appointment.id}

async def get_customer_appointments(customer_id: int, upcoming: bool = False) -> List[Dict]:
    async with AsyncSessionLocal() as db:
        query = select(Appointment, Service).join(Service, Appointment.service_id == Service.id).filter(Appointment.customer_id == customer_id)
        
        if upcoming:
            query = query.filter(Appointment.date >= datetime.now(), Appointment.status.in_(["P", "C"]))
            
        result = await db.execute(query.order_by(Appointment.date.asc()))
        
        appointments = []
        for appt, service in result.all():
            appointments.append({
                "id": appt.id,
                "service_id": appt.service_id,
                "service": appt.service_id,
                "service_name": service.name,
                "date": appt.date.strftime("%Y-%m-%d"),
                "time": appt.date.strftime("%I:%M %p").lstrip('0'),
                "start_at": appt.date.isoformat(),
                "status": appt.status
            })
        return appointments


async def get_customer_preferred_time_hhmm(customer_id: int) -> Optional[str]:
    """
    Hora preferida heurística del cliente (hh:mm), basada en historial confirmado/pendiente.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment)
            .filter(
                Appointment.customer_id == customer_id,
                Appointment.status.in_(["P", "C", "pending", "confirmed"]),
            )
            .order_by(Appointment.date.desc())
            .limit(50)
        )
        rows = result.scalars().all()
        if not rows:
            return None

        counts = {}
        for appt in rows:
            dt = appt.date
            hhmm = dt.strftime("%H:%M")
            counts[hhmm] = int(counts.get(hhmm, 0)) + 1

        best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return best

async def update_appointment(appointment_id: int, update_data: Dict) -> Dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Appointment).filter(Appointment.id == appointment_id))
        appointment = result.scalars().first()
        if appointment:
            start_at = datetime.fromisoformat(update_data["start_at"].replace('Z', '+00:00'))
            appointment.date = start_at
            await db.commit()
            return {"id": appointment.id, "date": appointment.date.isoformat()}
        return {}

async def cancel_appointment(appointment_id: int, notes: Optional[str] = None) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Appointment).filter(Appointment.id == appointment_id))
        appointment = result.scalars().first()
        if appointment:
            appointment.status = "A" # Canceled
            # If we had a notes field in the model, we could save it here
            await db.commit()
            return True
        return False

async def get_business_schedule(business_id: int) -> List[Dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ScheduleRule)
            .filter(ScheduleRule.business_id == business_id, ScheduleRule.is_available == True)
            .order_by(ScheduleRule.day_of_week.asc(), ScheduleRule.start_time.asc())
        )
        rules = result.scalars().all()

        if not rules:
            return [
                {"weekday": 0, "start_time": "09:00", "end_time": "18:00", "is_working_day": True},
                {"weekday": 1, "start_time": "09:00", "end_time": "18:00", "is_working_day": True},
                {"weekday": 2, "start_time": "09:00", "end_time": "18:00", "is_working_day": True},
                {"weekday": 3, "start_time": "09:00", "end_time": "18:00", "is_working_day": True},
                {"weekday": 4, "start_time": "09:00", "end_time": "18:00", "is_working_day": True},
            ]

        schedule = []
        for rule in rules:
            schedule.append(
                {
                    # Stored as Sunday=0 ... Saturday=6, but NLU formatter expects Monday=0.
                    "weekday": (rule.day_of_week - 1) % 7,
                    "start_time": rule.start_time.strftime("%H:%M"),
                    "end_time": rule.end_time.strftime("%H:%M"),
                    "is_working_day": bool(rule.is_available),
                }
            )
        return schedule


async def get_appointment_for_owner(appointment_id: int, business_id: int) -> Optional[Dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment).filter(
                Appointment.id == appointment_id,
                Appointment.business_id == business_id,
            )
        )
        appt = result.scalars().first()
        if not appt:
            return None
        return {"id": appt.id, "status": appt.status or "P", "business_id": appt.business_id}


async def mark_appointment_done(appointment_id: int, business_id: int) -> bool:
    """Mark appointment as completed (D). Only valid from P or C status."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment).filter(
                Appointment.id == appointment_id,
                Appointment.business_id == business_id,
            )
        )
        appt = result.scalars().first()
        if not appt or appt.status not in ("P", "C"):
            return False
        appt.status = "D"
        await db.commit()
        return True


async def get_active_appointments_in_window(
    business_id: int, start_utc: datetime, end_utc: datetime
) -> List[Dict]:
    """Return active appointments (P/C) that overlap with [start_utc, end_utc)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Appointment, Customer, Service)
            .join(Customer, Appointment.customer_id == Customer.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .filter(
                Appointment.business_id == business_id,
                Appointment.status.in_(["P", "C"]),
                Appointment.date >= start_utc,
                Appointment.date < end_utc,
            )
            .order_by(Appointment.date.asc())
        )
        rows = result.all()
        out = []
        for appt, customer, service in rows:
            out.append(
                {
                    "id": appt.id,
                    "date": appt.date.isoformat(),
                    "customer_name": customer.name if customer and customer.name else "Cliente",
                    "service_name": service.name if service else "Servicio",
                }
            )
        return out


async def create_time_block(
    business_id: int, start_at: datetime, end_at: datetime, reason: str = ""
) -> Dict:
    async with AsyncSessionLocal() as db:
        block = TimeBlock(
            business_id=business_id,
            start_at=start_at,
            end_at=end_at,
            reason=reason or None,
        )
        db.add(block)
        await db.commit()
        await db.refresh(block)
        return {"id": block.id, "start_at": block.start_at.isoformat(), "end_at": block.end_at.isoformat()}


async def toggle_business_notifications(business_id: int, owner_id: int) -> Optional[bool]:
    """Toggle daily_notification_enabled. Returns new value or None if not found/unauthorized."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business).filter(Business.id == business_id, Business.owner_id == owner_id)
        )
        business = result.scalars().first()
        if not business:
            return None
        business.daily_notification_enabled = not business.daily_notification_enabled
        await db.commit()
        return business.daily_notification_enabled
