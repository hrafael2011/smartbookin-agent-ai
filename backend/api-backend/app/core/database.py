import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

# Alembic imports this module before app.config; load api-backend/.env first.
_api_backend_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_api_backend_root / ".env")
load_dotenv()

# The .env file URL will be something like: postgresql://postgres:postgres@localhost:5432/smartbooking
# For SQLAlchemy asyncpg we need to replace postgresql:// with postgresql+asyncpg://
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/smartbooking")

# asyncpg (0.31+) no acepta `sslmode`/`channel_binding` como kwargs de connect();
# Neon incluye `sslmode=require` en sus cadenas. Traducimos sslmode → ssl="require"
# y quitamos los parámetros que asyncpg no entiende, sin cambiar el resto de la URL.
_db_url = make_url(DATABASE_URL)
_ASYNC_CONNECT_ARGS = {}
_sslmode = _db_url.query.get("sslmode")
if _sslmode in ("require", "verify-ca", "verify-full"):
    _ASYNC_CONNECT_ARGS["ssl"] = _sslmode
_clean_query = {
    k: v for k, v in _db_url.query.items() if k not in ("sslmode", "channel_binding")
}
ASYNC_DATABASE_URL = (
    _db_url.set(query=_clean_query).render_as_string(hide_password=False)
).replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(ASYNC_DATABASE_URL, connect_args=_ASYNC_CONNECT_ARGS, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
