import logging
from asyncio import get_event_loop

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Probe the database with a lightweight query to confirm connectivity."""
    async with engine.connect() as conn:
        await conn.execute(sa.text("SELECT 1"))


async def get_session() -> AsyncSession:  # type: ignore[return]
    """FastAPI dependency — yields a database session and closes it on completion."""
    async with async_session_factory() as session:
        yield session
