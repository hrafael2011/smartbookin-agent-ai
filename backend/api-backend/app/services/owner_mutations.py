"""Owner-channel mutation helpers: validate ownership/status then mutate via db_service."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.services import db_service

logger = logging.getLogger(__name__)

CANCELLABLE_STATUSES = {"P", "C"}
COMPLETABLE_STATUSES = {"P", "C"}
RESCHEDULABLE_STATUSES = {"P", "C"}


@dataclass(frozen=True)
class MutationResult:
    ok: bool
    error: Optional[str] = None


async def owner_cancel_appointment(appointment_id: int, business_id: int) -> MutationResult:
    appt = await db_service.get_appointment_for_owner(appointment_id, business_id)
    if not appt:
        return MutationResult(ok=False, error="not_found")
    if appt["status"] not in CANCELLABLE_STATUSES:
        return MutationResult(ok=False, error="not_cancellable")
    cancelled = await db_service.cancel_appointment(appointment_id, notes="Cancelado por el dueño vía Telegram")
    if not cancelled:
        return MutationResult(ok=False, error="cancel_failed")
    logger.info("owner_cancel appointment=%s business=%s", appointment_id, business_id)
    return MutationResult(ok=True)


async def owner_complete_appointment(appointment_id: int, business_id: int) -> MutationResult:
    appt = await db_service.get_appointment_for_owner(appointment_id, business_id)
    if not appt:
        return MutationResult(ok=False, error="not_found")
    if appt["status"] not in COMPLETABLE_STATUSES:
        return MutationResult(ok=False, error="not_completable")
    done = await db_service.mark_appointment_done(appointment_id, business_id)
    if not done:
        return MutationResult(ok=False, error="complete_failed")
    logger.info("owner_complete appointment=%s business=%s", appointment_id, business_id)
    return MutationResult(ok=True)


async def owner_reschedule_appointment(
    appointment_id: int, business_id: int, new_start_utc: str
) -> MutationResult:
    appt = await db_service.get_appointment_for_owner(appointment_id, business_id)
    if not appt:
        return MutationResult(ok=False, error="not_found")
    if appt["status"] not in RESCHEDULABLE_STATUSES:
        return MutationResult(ok=False, error="not_reschedulable")
    updated = await db_service.update_appointment(
        appointment_id, {"start_at": new_start_utc}
    )
    if not updated:
        return MutationResult(ok=False, error="reschedule_failed")
    logger.info("owner_reschedule appointment=%s business=%s new_start=%s", appointment_id, business_id, new_start_utc)
    return MutationResult(ok=True)


async def owner_block_timeslot(
    business_id: int,
    owner_id: int,
    start_at: datetime,
    end_at: datetime,
    reason: str = "",
) -> MutationResult:
    if start_at >= end_at:
        return MutationResult(ok=False, error="invalid_window")

    start_utc = start_at if start_at.tzinfo else start_at.replace(tzinfo=timezone.utc)
    end_utc = end_at if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc)

    conflicts = await db_service.get_active_appointments_in_window(business_id, start_utc, end_utc)
    if conflicts:
        names = ", ".join(c.get("customer_name", "?") for c in conflicts[:3])
        suffix = f" (+{len(conflicts)-3} más)" if len(conflicts) > 3 else ""
        return MutationResult(ok=False, error=f"conflict:{names}{suffix}")

    await db_service.create_time_block(business_id, start_utc, end_utc, reason)
    logger.info("owner_block business=%s start=%s end=%s", business_id, start_utc, end_utc)
    return MutationResult(ok=True)
