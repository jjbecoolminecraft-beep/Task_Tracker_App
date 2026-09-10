"""Async database engine and session management.

Locally we authenticate to PostgreSQL with a username/password from ``DATABASE_URL``.
In Azure the API uses its user-assigned Managed Identity to fetch a short-lived
Entra ID access token for PostgreSQL — no password anywhere (spec §6.3). That swap
happens here in ``_connect_args`` / an event listener; the rest of the app is
unaffected.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

_json_serializer = lambda obj: json.dumps(obj, default=str, separators=(",", ":"))  # noqa: E731

if settings.app_env == "test":
    # One fresh connection per checkout, closed immediately — pytest-asyncio runs
    # each test on its own event loop, and a pooled asyncpg connection cannot
    # outlive the loop it was opened on.
    engine: AsyncEngine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        poolclass=NullPool,
        json_serializer=_json_serializer,
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        # Audit before/after blobs can carry dates/UUIDs/Decimals; stringify
        # anything the stdlib encoder would refuse rather than 500 on a write.
        json_serializer=_json_serializer,
    )

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope: commit on success, roll back on error.

    Every mutation — including its audit event — runs inside one of these, so the
    change and its audit row commit together or not at all (spec §12).
    """
    session = SessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency form of :func:`session_scope`."""
    async with session_scope() as session:
        yield session
