"""Database engines and the request-scoped session.

psycopg 3 serves both the async engine (api) and the sync one (init, Alembic, later worker).
"""

from collections.abc import AsyncIterator
from typing import Annotated

import sqlalchemy
from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from sanad.core.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    # hide_parameters: a failed statement must not print its bound values to the log, such as
    # a question and its answer (query store) or a password hash (admin users).
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        hide_parameters=True,
    )


def create_sync_engine(settings: Settings) -> sqlalchemy.Engine:
    # hide_parameters: as above, for init (seed documents, demo password hashes) and Alembic.
    return sqlalchemy.create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)


async def ping(engine: AsyncEngine) -> None:
    """Raise if the database can't answer a trivial query."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, shared by every dependency of that request. Route code commits
    explicitly; anything uncommitted is rolled back when the request ends."""
    async with AsyncSession(request.app.state.db_engine, expire_on_commit=False) as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
