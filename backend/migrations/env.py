"""Alembic environment — async engine, URL from app settings."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from app.core.config import settings
from app.models import Base  # noqa: F401 - registers all tables on Base.metadata
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Objects created by raw SQL in a migration (not declared on a model) — exclude
# them from autogenerate so it doesn't propose dropping them every time.
_UNMANAGED_OBJECTS = {("index", "ix_tasks_search_vector")}


def _include_object(obj, name, type_, _reflected, _compare_to) -> bool:  # type: ignore[no-untyped-def]
    return (type_, name) not in _UNMANAGED_OBJECTS


def _run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.database_url},
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
