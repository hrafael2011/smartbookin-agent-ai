import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.config import config
from app.core.database import DATABASE_URL

logger = logging.getLogger(__name__)

# APScheduler necesita el driver SÍNCRONO. `DATABASE_URL` llega como
# `postgresql://...` (el sufijo `+asyncpg` lo añade database.py, y solo para el
# engine async), y SQLAlchemy >=2.1 resuelve `postgresql://` a psycopg3, que no
# está instalado. Forzamos psycopg2 explícitamente (ya es dependencia).
SYNC_DATABASE_URL = (
    DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    .replace("postgresql://", "postgresql+psycopg2://")
)

jobstores = {
    'default': SQLAlchemyJobStore(url=SYNC_DATABASE_URL)
}

scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=config.TIMEZONE)

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped")
