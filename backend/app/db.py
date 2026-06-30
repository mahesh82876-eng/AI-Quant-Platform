"""SQLAlchemy declarative base and engine configuration.

The database session is created here and shared via a dependency-injection
point (``get_session``). The ``Base`` is the single declarative base all
context-specific models inherit from.

Per ADR-0012, each bounded context owns a PostgreSQL schema. Cross-schema
access is the exception, not the norm.
"""

from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Single declarative base for all schemas."""
    pass


# Lazily-initialized engine/session — created once per process.
_engine = None
_session_factory = None


def init_engine() -> None:
    """Create the async engine and session factory from settings."""
    global _engine, _session_factory
    if _engine is not None:
        return
    settings = get_settings()
    _engine = create_async_engine(
        settings.db.dsn.replace("psycopg://", "postgresql+asyncpg://"),
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.pool_max_overflow,
        echo=False,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Yield a database session (FastAPI dependency)."""
    if _engine is None:
        init_engine()
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_engine():
    """Return the engine (for Alembic offline/metadata operations)."""
    if _engine is None:
        init_engine()
    return _engine
