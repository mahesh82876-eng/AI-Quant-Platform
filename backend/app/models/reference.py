"""Reference schema models: instruments and trading universe membership (ADR-0004).

This schema is the **read-only** foundation every context queries: symbols,
asset classes, sectors, and which universe a symbol belongs to. It is written
by admin processes (universe management) and read by every engine.

Per ADR-0012 this is the ``reference`` schema.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Instrument(Base):
    __tablename__ = "instrument"
    __table_args__ = (
        UniqueConstraint("symbol"),
        Index("ix_instrument_asset_class", "asset_class"),
        Index("ix_instrument_sector", "sector"),
        {"schema": "reference"},
    )

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    asset_class: Mapped[str] = mapped_column(String(32), default="equity")
    sector: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_index: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tick_size: Mapped[float] = mapped_column(Float, default=0.01)
    created_at: Mapped[date] = mapped_column(Date, default=date.today)


class Universe(Base):
    __tablename__ = "universe"
    __table_args__ = (
        UniqueConstraint("name"),
        {"schema": "reference"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UniverseMembership(Base):
    __tablename__ = "universe_membership"
    __table_args__ = (
        UniqueConstraint("universe_id", "symbol", "effective_from"),
        {"schema": "reference"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    universe_id: Mapped[int] = mapped_column(
        index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, default=date.today)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    def is_effective(self, as_of: date | None = None) -> bool:
        d = as_of or date.today()
        return d >= self.effective_from and (self.effective_to is None or d <= self.effective_to)
