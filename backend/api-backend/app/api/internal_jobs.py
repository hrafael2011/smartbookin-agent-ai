"""
Endpoints internos para el cron externo (fase 4 del MVP).

Cuando CRON_EXTERNAL=true el APScheduler en proceso no se registra; el cron
externo (Railway / GitHub Actions) dispara estos endpoints con el token
INTERNAL_CRON_TOKEN como `Authorization: Bearer <token>`.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Header

from app.config import config
from app.services.background_tasks import (
    process_appointment_reminders,
    process_waitlist_expiration,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/jobs", tags=["Internal"])


async def _check_cron_token(authorization: str = Header(default="")) -> None:
    if not config.INTERNAL_CRON_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Cron interno no configurado (INTERNAL_CRON_TOKEN vacío)",
        )
    if authorization != f"Bearer {config.INTERNAL_CRON_TOKEN}":
        raise HTTPException(status_code=401, detail="Token inválido")


@router.post("/reminders", dependencies=[Depends(_check_cron_token)])
async def run_reminders():
    """Recordatorios 24h/2h. Cron: cada ~10-30 min."""
    await process_appointment_reminders()
    return {"status": "ok", "job": "reminders"}


@router.post("/waitlist-expiration", dependencies=[Depends(_check_cron_token)])
async def run_waitlist_expiration():
    """Expiración de waitlist. Solo si WAITLIST_ENABLED=true (diferida en MVP)."""
    if not config.WAITLIST_ENABLED:
        raise HTTPException(status_code=404, detail="Waitlist diferida (WAITLIST_ENABLED=false)")
    await process_waitlist_expiration()
    return {"status": "ok", "job": "waitlist-expiration"}
