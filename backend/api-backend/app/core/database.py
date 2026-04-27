import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# Alembic imports this module before app.config; load api-backend/.env first.
_api_backend_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_api_backend_root / ".env")
load_dotenv()

# The .env file URL will be something like: postgresql://postgres:postgres@localhost:5432/smartbooking
# For SQLAlchemy asyncpg we need to replace postgresql:// with postgresql+asyncpg://
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/smartbooking")
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
