"""Domain value objects and enumerations.

These are the atoms of the quant domain. They are frozen (hashable, immutable)
and validated by Pydantic v2 so a malformed bar or order can never enter the
engines. Money is represented as plain ``float`` (USD) throughout the domain;
for an institutional system we'd use a Decimal-based Money type, but float is
sufficient for the simulation tier and keeps the domain NumPy-friendly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Iterator

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ──────────────────────────────── Enums ────────────────────────────────


class Side(StrEnum):
    """Direction of a position or trade."""

    LONG = "long"
    SHORT = "short"


class OrderSide(StrEnum):
    """Buy/sell direction of an order.

    Distinct from :class:`Side` because a *buy* can open a long OR close a
    short; conflating them is a classic source of risk bugs.
    """

    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    """Order types supported by the execution layer (ADR-0005)."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    BRACKET = "bracket"


class OrderStatus(StrEnum):
    """Lifecycle of an order."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class AssetClass(StrEnum):
    """Top-level classification of an instrument."""

    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    FOREX = "forex"
    CRYPTO = "crypto"


# ──────────────────────────────── Instrument ────────────────────────────


class Instrument(BaseModel):
    """A tradable or observable asset (ADR-0004).

    ``is_index`` is the structural guard that prevents indices from ever
    generating a tradeable signal (ARCHITECTURE.md §7).
    """

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., min_length=1, max_length=16, description="Ticker, e.g. AAPL")
    name: str = Field(default="", description="Human-readable name")
    asset_class: AssetClass = AssetClass.EQUITY
    sector: str | None = None
    is_index: bool = False
    currency: str = Field(default="USD", min_length=3, max_length=3)
    tick_size: float = Field(default=0.01, gt=0)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        return v.upper().strip()


# ──────────────────────────────── Market data ────────────────────────────


class Bar(BaseModel):
    """A single OHLCV bar for one instrument at one timestamp.

    Timestamps are UTC, second-or-finer. ``volume`` is non-negative. We
    validate the OHLCV invariant (low ≤ {open, close} ≤ high) because a
    backtest fed bad bars produces silently wrong results.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    symbol: str
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @field_validator("high")
    @classmethod
    def _high_is_extreme(cls, high: float, info) -> float:  # type: ignore[no-untyped-def]
        o = info.data.get("open")
        if o is not None and high < o:
            raise ValueError(f"high ({high}) < open ({o})")
        return high

    @field_validator("low")
    @classmethod
    def _low_is_extreme(cls, low: float, info) -> float:  # type: ignore[no-untyped-def]
        o = info.data.get("open")
        if o is not None and low > o:
            raise ValueError(f"low ({low}) > open ({o})")
        return low

    @field_validator("close")
    @classmethod
    def _close_in_range(cls, close: float, info) -> float:  # type: ignore[no-untyped-def]
        high, low = info.data.get("high"), info.data.get("low")
        if high is not None and close > high:
            raise ValueError(f"close ({close}) > high ({high})")
        if low is not None and close < low:
            raise ValueError(f"close ({close}) < low ({low})")
        return close


class BarSeries(BaseModel):
    """An ordered, gap-aware time series of bars for one symbol.

    Bars must be strictly ascending by timestamp and all share one symbol.
    Acts as a lightweight, dependency-free alternative to a pandas DataFrame
    inside the pure domain; the ML/research tier can convert to a DataFrame
    at the boundary.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    bars: list[Bar] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def _norm(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("bars")
    @classmethod
    def _check_strictly_ascending(cls, bars: list[Bar]) -> list[Bar]:
        for prev, cur in zip(bars, bars[1:], strict=False):
            if cur.timestamp <= prev.timestamp:
                raise ValueError(
                    f"bars must be strictly ascending; {cur.timestamp} <= {prev.timestamp}"
                )
        return bars

    def __len__(self) -> int:
        return len(self.bars)

    def __iter__(self) -> Iterator[Bar]:  # type: ignore[override]
        return iter(self.bars)

    def __getitem__(self, idx: int) -> Bar:
        return self.bars[idx]

    @property
    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    @property
    def timestamps(self) -> list[datetime]:
        return [b.timestamp for b in self.bars]

    @property
    def empty(self) -> bool:
        return not self.bars

    def head(self, n: int) -> BarSeries:
        """First ``n`` bars (a new immutable series)."""
        return BarSeries(symbol=self.symbol, bars=self.bars[:n])

    def slice_until(self, timestamp: datetime) -> BarSeries:
        """Bars strictly before ``timestamp`` — the strict "information set"."""
        return BarSeries(symbol=self.symbol, bars=[b for b in self.bars if b.timestamp < timestamp])

    def slice_through(self, timestamp: datetime) -> BarSeries:
        """Bars up to and including ``timestamp`` — the information set at a bar close.

        Used by the daily-bar backtest: a strategy sees the bar ending at
        ``timestamp`` and trades at its close. No lookahead because the fill
        price is that same bar's close.
        """
        return BarSeries(symbol=self.symbol, bars=[b for b in self.bars if b.timestamp <= timestamp])


class MarketData(BaseModel):
    """A collection of :class:`BarSeries`, keyed by symbol.

    The natural input to a backtest or live run: "here is everything the
    strategy is allowed to see."
    """

    model_config = ConfigDict(frozen=True)

    series: dict[str, BarSeries] = Field(default_factory=dict)

    def add(self, s: BarSeries) -> MarketData:
        """Return a new MarketData with ``s`` merged in (immutable update)."""
        return MarketData(series={**self.series, s.symbol: s})

    def get(self, symbol: str) -> BarSeries | None:
        return self.series.get(symbol.upper())

    @property
    def symbols(self) -> list[str]:
        return list(self.series)

    def slice_until(self, timestamp: datetime) -> MarketData:
        """Everything observable strictly before ``timestamp`` (no lookahead)."""
        return MarketData(
            series={sym: bs.slice_until(timestamp) for sym, bs in self.series.items()}
        )

    def slice_through(self, timestamp: datetime) -> MarketData:
        """Everything observable up to and including ``timestamp`` (bar-close view)."""
        return MarketData(
            series={sym: bs.slice_through(timestamp) for sym, bs in self.series.items()}
        )


def utcnow() -> datetime:
    """Timezone-aware now, for deterministic clock injection in tests."""
    return datetime.now(timezone.utc)
