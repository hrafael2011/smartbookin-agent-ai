import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.core.database import DATABASE_URL

logger = logging.getLogger(__name__)

# Use standard sync database URL for APScheduler job store
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

jobstores = {
    'default': SQLAlchemyJobStore(url=SYNC_DATABASE_URL)
}

scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="America/Santo_Domingo")

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped")
