"""Deterministic calendar menu handlers for future booking dates."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.services import db_service
from app.services.conversation_manager import conversation_manager
from app.utils.conversation_routing import guided_menu
from app.utils.date_parse import (
    DEFAULT_OPERATIONAL_TZ,
    format_month_label,
    format_week_label,
)


def _today() -> date:
    return datetime.now(DEFAULT_OPERATIONAL_TZ).date()


def _month_shift(base: date, offset: int) -> tuple[int, int]:
    month_zero = base.month - 1 + offset
    year = base.year + month_zero // 12
    month = month_zero % 12 + 1
    return year, month


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _weeks_for_month(year: int, month: int) -> List[Dict]:
    start, end = _month_bounds(year, month)
    cursor = start
    weeks: List[Dict] = []
    while cursor <= end:
        week_start = cursor - timedelta(days=cursor.weekday())
        week_end = week_start + timedelta(days=6)
        clamped_start = max(week_start, start)
        clamped_end = min(week_end, end)
        weeks.append({"start": clamped_start, "end": clamped_end})
        cursor = clamped_end + timedelta(days=1)
    return weeks


def _numbered_days(days: List[Dict]) -> str:
    return "\n".join(f"  {i}. {day['label']}" for i, day in enumerate(days, 1))


async def handle_booking_current_week(
    business_id: int,
    user_key: str,
    service_id: int,
    context: Dict,
    *,
    reset_stack: bool = False,
) -> str:
    pending_data = dict(context.get("pending_data") or {})
    pending_data["service_id"] = service_id

    start = _today()
    end = start + timedelta(days=6 - start.weekday())
    days = await db_service.get_available_days_in_range(
        business_id=business_id,
        service_id=service_id,
        start_date=start,
        end_date=end,
    )
    if not days:
        context_for_month = {**context, "pending_data": pending_data}
        return await handle_booking_month(business_id, user_key, context_for_month)

    pending_data["calendar_days"] = days
    payload = {
        "current_intent": "book_appointment",
        "state": "booking_current_week",
        "pending_data": pending_data,
    }
    if reset_stack:
        payload["state_stack"] = []
    await conversation_manager.update_context(business_id, user_key, payload)
    return (
        "¿Para qué día querés tu cita?\n\n"
        "Esta semana:\n"
        f"{_numbered_days(days)}\n\n"
        "  8) Buscar en otro mes\n"
        "  9) Volver\n"
        "  0) Menú principal"
    )


async def handle_booking_month(
    business_id: int,
    user_key: str,
    context: Dict,
    *,
    months_ahead: int = 3,
) -> str:
    pending_data = dict(context.get("pending_data") or {})
    service_id = int(pending_data.get("service_id") or 0)
    if not service_id:
        await conversation_manager.update_context(
            business_id,
            user_key,
            {
                "current_intent": "book_appointment",
                "state": "awaiting_service",
                "pending_data": pending_data,
            },
        )
        return "Necesito confirmar el servicio antes de buscar fechas.\n\n9) Volver\n0) Menú principal"

    base = _today()
    months: List[Dict] = []
    for offset in range(1, months_ahead + 1):
        year, month = _month_shift(base, offset)
        start, end = _month_bounds(year, month)
        days = await db_service.get_available_days_in_range(
            business_id=business_id,
            service_id=service_id,
            start_date=start,
            end_date=end,
        )
        if days:
            months.append(
                {
                    "index": len(months) + 1,
                    "year": year,
                    "month": month,
                    "label": format_month_label(year, month),
                }
            )

    pending_data["calendar_months"] = months
    await conversation_manager.update_context(
        business_id,
        user_key,
        {
            "current_intent": "book_appointment",
            "state": "booking_month",
            "pending_data": pending_data,
        },
    )

    if not months:
        await conversation_manager.update_context(
            business_id,
            user_key,
            {
                "current_intent": None,
                "state": "idle",
                "pending_data": {},
                "state_stack": [],
            },
        )
        return (
            "No encontré disponibilidad en los próximos 3 meses.\n\n"
            f"{guided_menu(context.get('customer_name') or '')}"
        )

    lines = "\n".join(f"  {item['index']}. {item['label']}" for item in months)
    return (
        "¿En qué mes querés agendar?\n\n"
        f"{lines}\n\n"
        "  9) Volver\n"
        "  0) Menú principal"
    )


async def handle_booking_week(
    business_id: int,
    user_key: str,
    month_index: int,
    context: Dict,
) -> str:
    pending_data = dict(context.get("pending_data") or {})
    service_id = int(pending_data.get("service_id") or 0)
    months = list(pending_data.get("calendar_months") or [])
    selected = next((m for m in months if int(m.get("index")) == month_index), None)
    if not selected or not service_id:
        return "No entendí el mes elegido. Respondé con una opción de la lista."

    weeks: List[Dict] = []
    for week in _weeks_for_month(int(selected["year"]), int(selected["month"])):
        days = await db_service.get_available_days_in_range(
            business_id=business_id,
            service_id=service_id,
            start_date=week["start"],
            end_date=week["end"],
        )
        if days:
            weeks.append(
                {
                    "index": len(weeks) + 1,
                    "start": week["start"].isoformat(),
                    "end": week["end"].isoformat(),
                    "label": format_week_label(week["start"], week["end"]),
                    "day_count": len(days),
                }
            )

    pending_data["calendar_weeks"] = weeks
    pending_data["calendar_selected_month"] = selected
    await conversation_manager.update_context(
        business_id,
        user_key,
        {
            "current_intent": "book_appointment",
            "state": "booking_week",
            "pending_data": pending_data,
        },
    )

    if not weeks:
        return "Ese mes ya no tiene semanas disponibles. Probá con otro mes.\n\n9) Volver\n0) Menú principal"

    lines = "\n".join(
        f"  {w['index']}. {w['label']} ({w['day_count']} días disponibles)"
        for w in weeks
    )
    return (
        f"¿Qué semana de {selected['label'].lower()}?\n\n"
        f"{lines}\n\n"
        "  9) Volver\n"
        "  0) Menú principal"
    )


async def handle_booking_day(
    business_id: int,
    user_key: str,
    week_index: int,
    context: Dict,
) -> str:
    pending_data = dict(context.get("pending_data") or {})
    service_id = int(pending_data.get("service_id") or 0)
    weeks = list(pending_data.get("calendar_weeks") or [])
    selected = next((w for w in weeks if int(w.get("index")) == week_index), None)
    if not selected or not service_id:
        return "No entendí la semana elegida. Respondé con una opción de la lista."

    days = await db_service.get_available_days_in_range(
        business_id=business_id,
        service_id=service_id,
        start_date=date.fromisoformat(selected["start"]),
        end_date=date.fromisoformat(selected["end"]),
    )
    pending_data["calendar_days"] = days
    pending_data["calendar_selected_week"] = selected
    await conversation_manager.update_context(
        business_id,
        user_key,
        {
            "current_intent": "book_appointment",
            "state": "booking_day",
            "pending_data": pending_data,
        },
    )

    if not days:
        return "Esa semana ya no tiene días disponibles. Probá con otra semana.\n\n9) Volver\n0) Menú principal"

    return (
        "¿Qué día de esa semana?\n\n"
        f"{_numbered_days(days)}\n\n"
        "  9) Volver\n"
        "  0) Menú principal"
    )


def selected_calendar_day(context: Dict, raw_text: str) -> Optional[Dict]:
    text = str(raw_text or "").strip()
    if not text.isdigit():
        return None
    idx = int(text)
    days = list((context.get("pending_data") or {}).get("calendar_days") or [])
    if 1 <= idx <= len(days):
        return days[idx - 1]
    return None
