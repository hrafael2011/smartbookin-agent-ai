"""Read-only owner channel queries for agenda and daily metrics."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Appointment, Business, Customer, Service

OWNER_TIMEZONE = ZoneInfo("America/Santo_Domingo")
_DEFAULT_TZ_NAME = "America/Santo_Domingo"

ACTIVE_STATUSES = {"P", "C"}
ESTIMATED_REVENUE_STATUSES = {"P", "C"}
REALIZED_REVENUE_STATUSES = {"D"}

STATUS_LABELS = {
    "P": "pendiente",
    "C": "confirmada",
    "A": "cancelada",
    "D": "completada",
    "pending": "pendiente",
    "confirmed": "confirmada",
    "cancelled": "cancelada",
    "canceled": "cancelada",
    "completed": "completada",
}


def _resolve_tz(tz_name: Optional[str]) -> ZoneInfo:
    if not tz_name:
        return OWNER_TIMEZONE
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return OWNER_TIMEZONE


def local_today(tz: ZoneInfo = OWNER_TIMEZONE) -> date:
    return datetime.now(tz).date()


def _status_code(status: Optional[str]) -> str:
    raw = str(status or "P").strip()
    lowered = raw.lower()
    reverse = {
        "pending": "P",
        "confirmed": "C",
        "cancelled": "A",
        "canceled": "A",
        "completed": "D",
    }
    return reverse.get(lowered, raw.upper())


def status_label(status: Optional[str]) -> str:
    raw = str(status or "P").strip()
    return STATUS_LABELS.get(raw, STATUS_LABELS.get(raw.lower(), raw or "pendiente"))


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_day_window(target_day: date, tz: ZoneInfo = OWNER_TIMEZONE) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_day, datetime.min.time(), tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _local_time(value: datetime, tz: ZoneInfo = OWNER_TIMEZONE) -> str:
    return _as_aware_utc(value).astimezone(tz).strftime("%I:%M %p").lstrip("0")


def _money(value: Optional[float]) -> str:
    return f"${float(value or 0):.2f}"


async def _assert_owner_business(owner_id: int, business_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Business.id).filter(
                Business.id == business_id,
                Business.owner_id == owner_id,
            )
        )
        return result.scalars().first() is not None


def _agenda_item(appointment: Appointment, customer: Optional[Customer], service: Optional[Service], tz: ZoneInfo = OWNER_TIMEZONE) -> dict:
    if service is None:
        logger.warning("_agenda_item: service=None for appointment_id=%s", appointment.id)
    return {
        "appointment_id": appointment.id,
        "local_time": _local_time(appointment.date, tz),
        "customer_name": (customer.name if customer and customer.name else "Cliente sin nombre"),
        "customer_phone": (customer.phone_number if customer else ""),
        "service_name": (service.name if service else "Servicio no disponible"),
        "service_id": service.id if service else None,
        "status": appointment.status or "P",
        "status_label": status_label(appointment.status),
        "price": float(service.price or 0) if service else 0.0,
    }


async def list_owner_agenda(
    *,
    owner_id: int,
    business_id: int,
    target_day: date,
    limit: int = 20,
    tz_name: str = _DEFAULT_TZ_NAME,
) -> list[dict]:
    tz = _resolve_tz(tz_name)
    if not await _assert_owner_business(owner_id, business_id):
        return []

    start_utc, end_utc = _local_day_window(target_day, tz)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Appointment, Customer, Service)
            .join(Customer, Appointment.customer_id == Customer.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .filter(
                Appointment.business_id == business_id,
                Appointment.date >= start_utc,
                Appointment.date < end_utc,
            )
            .order_by(Appointment.date.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [_agenda_item(appt, customer, service, tz) for appt, customer, service in result.all()]


async def list_owner_upcoming(
    *,
    owner_id: int,
    business_id: int,
    limit: int = 10,
    tz_name: str = _DEFAULT_TZ_NAME,
) -> list[dict]:
    tz = _resolve_tz(tz_name)
    if not await _assert_owner_business(owner_id, business_id):
        return []

    now_utc = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Appointment, Customer, Service)
            .join(Customer, Appointment.customer_id == Customer.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .filter(
                Appointment.business_id == business_id,
                Appointment.date >= now_utc,
                Appointment.status.in_(list(ACTIVE_STATUSES)),
            )
            .order_by(Appointment.date.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [_agenda_item(appt, customer, service, tz) for appt, customer, service in result.all()]


def calculate_daily_metrics(items: Iterable[dict]) -> dict:
    metrics = {
        "total_appointments": 0,
        "pending": 0,
        "confirmed": 0,
        "completed": 0,
        "cancelled": 0,
        "estimated_revenue": 0.0,
        "realized_revenue": 0.0,
    }
    for item in items:
        metrics["total_appointments"] += 1
        code = _status_code(item.get("status"))
        price = float(item.get("price") or 0)
        if code == "P":
            metrics["pending"] += 1
        elif code == "C":
            metrics["confirmed"] += 1
        elif code == "D":
            metrics["completed"] += 1
        elif code == "A":
            metrics["cancelled"] += 1

        if code in ESTIMATED_REVENUE_STATUSES:
            metrics["estimated_revenue"] += price
        if code in REALIZED_REVENUE_STATUSES:
            metrics["realized_revenue"] += price
    return metrics


async def get_owner_daily_metrics(
    *,
    owner_id: int,
    business_id: int,
    target_day: date,
    tz_name: str = _DEFAULT_TZ_NAME,
) -> dict:
    if not await _assert_owner_business(owner_id, business_id):
        return calculate_daily_metrics([])
    items = await list_owner_agenda(
        owner_id=owner_id,
        business_id=business_id,
        target_day=target_day,
        limit=500,
        tz_name=tz_name,
    )
    return calculate_daily_metrics(items)


def format_agenda_response(title: str, items: list[dict]) -> str:
    if not items:
        return f"{title}\n\nNo hay citas registradas para ese periodo.\n\n9) Volver\n0) Menú principal\nX) Salir"

    lines = [title, ""]
    for index, item in enumerate(items, 1):
        phone = f" - {item['customer_phone']}" if item.get("customer_phone") else ""
        lines.append(
            f"{index}) {item['local_time']} - {item['customer_name']}{phone}\n"
            f"   {item['service_name']} | {item['status_label']} | {_money(item.get('price'))}"
        )
    lines.append("")
    lines.append("Escribí el número de una cita para ver detalle.")
    lines.append("9) Volver")
    lines.append("0) Menú principal")
    lines.append("X) Salir")
    return "\n".join(lines)


_VALID_STATUS_CODES = {"P", "C", "A", "D"}


def format_appointment_detail(item: dict) -> str:
    phone = item.get("customer_phone") or "No registrado"
    status_code = _status_code(item.get("status"))
    if status_code not in _VALID_STATUS_CODES:
        logger.warning("format_appointment_detail: unknown status_code=%r appointment_id=%s", status_code, item.get("appointment_id"))
    action_lines = ""
    if status_code in ("P", "C"):
        action_lines = "\nC) Cancelar esta cita\nM) Marcar como completada\nR) Reagendar\n"
    return (
        f"Cita #{item.get('appointment_id')}\n\n"
        f"Hora: {item.get('local_time')}\n"
        f"Cliente: {item.get('customer_name')}\n"
        f"Teléfono: {phone}\n"
        f"Servicio: {item.get('service_name')}\n"
        f"Estado: {item.get('status_label')}\n"
        f"Precio: {_money(item.get('price'))}\n"
        f"{action_lines}"
        "\n9) Volver\n0) Menú principal\nX) Salir"
    )


def format_metrics_response(title: str, metrics: dict) -> str:
    return (
        f"{title}\n\n"
        f"Citas totales: {metrics['total_appointments']}\n"
        f"Pendientes: {metrics['pending']}\n"
        f"Confirmadas: {metrics['confirmed']}\n"
        f"Completadas: {metrics['completed']}\n"
        f"Canceladas: {metrics['cancelled']}\n"
        f"Ingreso estimado: {_money(metrics['estimated_revenue'])}\n"
        f"Ingreso realizado: {_money(metrics['realized_revenue'])}\n\n"
        "9) Volver\n0) Menú principal\nX) Salir"
    )
