"""Market data schema: OHLCV bars stored as a TimescaleDB hypertable (ADR-0002).

Each row is one bar (day or sub-day) for one instrument. The ``timestamp``
column is the TimescaleDB partitioning key. This is the only table in this
schema that every engine reads from; it is written exclusively by the market
data ingestion adapter.

Per ADR-0012 this is the ``market_data`` schema.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OhlcvBar(Base):
    __tablename__ = "ohlcv_bar"
    __table_args__ = (
        UniqueConstraint("symbol", "timestamp"),
        Index("ix_ohlcv_symbol_ts", "symbol", "timestamp"),
        {"schema": "market_data"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
