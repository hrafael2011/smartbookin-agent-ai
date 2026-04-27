import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.models import Appointment, WaitlistEntry, Business

logger = logging.getLogger(__name__)

async def process_appointment_reminders():
    """Send 24h and 2h reminders"""
    logger.info("Running appointment reminders job...")
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        
        # 24h reminders
        target_24h_start = now + timedelta(hours=23, minutes=30)
        target_24h_end = now + timedelta(hours=24, minutes=30)
        
        # 2h reminders
        target_2h_start = now + timedelta(hours=1, minutes=30)
        target_2h_end = now + timedelta(hours=2, minutes=30)

        # Logic to fetch and send reminders would go here.
        # Ensure we check status == 'C' or 'P' and flags reminder_24h_sent / reminder_2h_sent.

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
