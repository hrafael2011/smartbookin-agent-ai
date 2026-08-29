import html
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models import Appointment, Customer, Service, WaitlistEntry, Business
from app.services import db_service
from app.services.telegram_client import telegram_client
from app.utils.date_parse import format_date_human_es

logger = logging.getLogger(__name__)

REMINDER_CADENCE_MINUTES = 15


def _reminder_windows(now: datetime) -> dict:
    """Ventanas de 24h y 2h (ancho = cadencia ±15 min) en el convenio wall-clock-as-UTC."""
    return {
        "start_24h": now + timedelta(hours=23, minutes=60 - REMINDER_CADENCE_MINUTES),
        "end_24h": now + timedelta(hours=24, minutes=REMINDER_CADENCE_MINUTES),
        "start_2h": now + timedelta(hours=1, minutes=60 - REMINDER_CADENCE_MINUTES),
        "end_2h": now + timedelta(hours=2, minutes=REMINDER_CADENCE_MINUTES),
    }

async def process_appointment_reminders():
    """Send 24h and 2h reminders (precisión ±15 min, convenio wall-clock-as-UTC)."""
    logger.info("Running appointment reminders job...")
    now = db_service._upcoming_now()
    windows = _reminder_windows(now)

    async with AsyncSessionLocal() as db:
        # 24h reminders
        await _send_window_reminders(db, windows["start_24h"], windows["end_24h"], "24h", "reminder_24h_sent")
        # 2h reminders
        await _send_window_reminders(db, windows["start_2h"], windows["end_2h"], "2h", "reminder_2h_sent")


async def _send_window_reminders(db, window_start, window_end, label, flag_attr):
    result = await db.execute(
        select(Appointment, Customer, Service, Business)
        .join(Customer, Appointment.customer_id == Customer.id, isouter=True)
        .join(Service, Appointment.service_id == Service.id, isouter=True)
        .join(Business, Appointment.business_id == Business.id, isouter=True)
        .filter(
            Appointment.status.in_(["P", "C"]),
            Appointment.date >= window_start,
            Appointment.date <= window_end,
            getattr(Appointment, flag_attr) == False,
        )
    )
    for appt, customer, service, business in result.all():
        phone = (customer.phone_number if customer else "") or ""
        if not phone.startswith("tg:"):
            logger.info("reminder_skip_non_tg business=%s appt=%s phone=%s", appt.business_id, appt.id, phone[:20])
            continue
        chat_id = phone[3:]
        message = (
            "📅 <b>Recordatorio de tu cita</b>\n\n"
            f"📍 {html.escape((business.name if business else '') or 'Negocio')}\n"
            f"✂️ {html.escape(service.name if service else 'Servicio')}\n"
            f"📅 {format_date_human_es(appt.date.strftime('%Y-%m-%d'))}\n"
            f"⏰ {appt.date.strftime('%I:%M %p').lstrip('0')}\n"
        )
        if business and business.address:
            message += f"    {html.escape(business.address)}\n"
        try:
            await telegram_client.send_text_message(chat_id=chat_id, message=message)
            setattr(appt, flag_attr, True)
            await db.commit()
            logger.info(
                "reminder_sent kind=%s appt=%s chat=%s business=%s",
                label, appt.id, chat_id, appt.business_id,
            )
        except Exception:
            logger.exception("reminder_send_failed kind=%s appt=%s chat=%s", label, appt.id, chat_id)
            await db.rollback()

async def process_waitlist_expiration():
    """Expire waitlist entries that haven't been fulfilled"""
    logger.info("Running waitlist expiration job...")
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(WaitlistEntry).filter(
                WaitlistEntry.status == "waiting",
                WaitlistEntry.date < now
            )
        )
        expired_entries = result.scalars().all()
        for entry in expired_entries:
            entry.status = "expired"
        
        if expired_entries:
            await db.commit()
            logger.info(f"Expired {len(expired_entries)} waitlist entries.")

async def generate_daily_agenda():
    """Generate and send daily agenda to business owners"""
    logger.info("Running daily agenda generation job...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Business).filter(Business.daily_notification_enabled == True))
        businesses = result.scalars().all()
        # Logic to fetch today's appointments and send via WhatsApp/Email to the owner.
