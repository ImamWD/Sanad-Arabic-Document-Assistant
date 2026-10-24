"""Database engine.

psycopg 3 serves both the async engine (api) and, later, a sync one (worker, Alembic).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from sanad.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


async def ping(engine: AsyncEngine) -> None:
    """Raise if the database can't answer a trivial query."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
