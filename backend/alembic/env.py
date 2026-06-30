"""Alembic environment — wired to our async engine and all schema models.

Imports every model so autogenerate sees them; reads the DB URL from
app.config (falling back to the alembic.ini sqlalchemy.url for offline use).
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Load all models so autogenerate sees every table.
from app.db import Base
import app.models  # noqa: F401 — registers all model metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from env if not set in alembic.ini.
if not config.get_main_option("sqlalchemy.url"):
    # Must load .env before importing settings outside the app lifecycle.
    from app.config import get_settings as _gs
    _s = _gs()
    sync_dsn = _s.db.dsn.replace("+psycopg", "+psycopg2", 1)
    config.set_main_option("sqlalchemy.url", sync_dsn)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
