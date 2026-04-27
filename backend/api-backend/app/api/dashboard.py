from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.dependencies import get_current_owner
from app.models import Appointment, Business, Owner, Service

router = APIRouter()


def _to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)


def _month_window(now_local: datetime) -> tuple[datetime, datetime]:
    start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


@router.get("/metrics/")
async def get_dashboard_metrics(
    business_id: int,
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

    tz = ZoneInfo("America/Santo_Domingo")
    now_local = datetime.now(tz)
    today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end_local = today_start_local + timedelta(days=1)
    week_start_local = today_start_local - timedelta(days=today_start_local.weekday())
    week_end_local = week_start_local + timedelta(days=7)
    month_start_local, month_end_local = _month_window(now_local)

    today_start = _to_utc(today_start_local)
    today_end = _to_utc(today_end_local)
    week_start = _to_utc(week_start_local)
    week_end = _to_utc(week_end_local)
    month_start = _to_utc(month_start_local)
    month_end = _to_utc(month_end_local)

    async def _count_between(start: datetime, end: datetime, statuses: list[str] | None = None) -> int:
        stmt = select(func.count(Appointment.id)).filter(
            Appointment.business_id == business_id,
            Appointment.date >= start,
            Appointment.date < end,
        )
        if statuses:
            stmt = stmt.filter(Appointment.status.in_(statuses))
        res = await db.execute(stmt)
        return int(res.scalar() or 0)

    async def _revenue_between(start: datetime, end: datetime) -> float:
        stmt = (
            select(func.coalesce(func.sum(Service.price), 0.0))
            .select_from(Appointment)
            .join(Service, Appointment.service_id == Service.id)
            .filter(
                Appointment.business_id == business_id,
                Appointment.date >= start,
                Appointment.date < end,
                Appointment.status.in_(["C", "D"]),
            )
        )
        res = await db.execute(stmt)
        return float(res.scalar() or 0.0)

    today_total = await _count_between(today_start, today_end)
    today_confirmed = await _count_between(today_start, today_end, ["C"])
    today_pending = await _count_between(today_start, today_end, ["P"])
    today_cancelled = await _count_between(today_start, today_end, ["A"])
    today_revenue = await _revenue_between(today_start, today_end)

    week_total = await _count_between(week_start, week_end)
    week_revenue = await _revenue_between(week_start, week_end)
    week_confirmed = await _count_between(week_start, week_end, ["C", "D"])
    occupancy_rate = round((week_confirmed / week_total) * 100, 2) if week_total else 0.0

    month_total = await _count_between(month_start, month_end)
    month_revenue = await _revenue_between(month_start, month_end)

    month_new_customers_stmt = select(func.count(func.distinct(Appointment.customer_id))).filter(
        Appointment.business_id == business_id,
        Appointment.date >= month_start,
        Appointment.date < month_end,
    )
    month_new_customers_res = await db.execute(month_new_customers_stmt)
    month_new_customers = int(month_new_customers_res.scalar() or 0)

    top_services_stmt = (
        select(
            Service.name,
            func.count(Appointment.id).label("count"),
            func.coalesce(func.sum(Service.price), 0.0).label("revenue"),
        )
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .filter(
            Appointment.business_id == business_id,
            Appointment.date >= month_start,
            Appointment.date < month_end,
            Appointment.status.in_(["C", "D"]),
        )
        .group_by(Service.id, Service.name)
        .order_by(func.count(Appointment.id).desc())
        .limit(5)
    )
    top_services_res = await db.execute(top_services_stmt)
    top_services = [
        {
            "service_name": name,
            "count": int(count),
            "revenue": f"{float(revenue):.2f}",
        }
        for name, count, revenue in top_services_res.all()
    ]

    return {
        "today": {
            "total_appointments": today_total,
            "confirmed": today_confirmed,
            "pending": today_pending,
            "cancelled": today_cancelled,
            "revenue": f"{today_revenue:.2f}",
        },
        "week": {
            "total_appointments": week_total,
            "revenue": f"{week_revenue:.2f}",
            "occupancy_rate": occupancy_rate,
        },
        "month": {
            "total_appointments": month_total,
            "revenue": f"{month_revenue:.2f}",
            "new_customers": month_new_customers,
        },
        "top_services": top_services,
        "recent_appointments": [],
        "upcoming_appointments": [],
    }
