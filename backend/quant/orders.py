"""Signals, orders, and fills — the action layer of the quant domain.

A *Signal* is what a strategy emits: an *intent* to trade, expressed as a
target weight or a delta. A *Order* is the concrete request the execution
layer acts on. A *Fill* is the realized execution. Keeping these three
distinct is what allows the same strategy to run in backtest and live
(ADR-0007): the strategy emits signals, the runtime translates them to
orders, the fill model / broker produces fills.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from quant.types import OrderSide, OrderType, Side, utcnow


# ──────────────────────────────── Signal ────────────────────────────────


class SignalType(StrEnum):
    """How a strategy expresses its intent.

    TARGET_WEIGHT: "I want symbol X to be ``weight`` fraction of NAV" — the
    default for portfolio-oriented strategies.
    DELTA_SHARES: "Buy/sell ``quantity`` shares of X" — for single-name logic.
    """

    TARGET_WEIGHT = "target_weight"
    DELTA_SHARES = "delta_shares"


class Signal(BaseModel):
    """A strategy's intent to trade one symbol.

    Signals are immutable and timestamped. Exactly one of ``weight`` /
    ``quantity`` is meaningful, selected by ``kind``. The risk engine
    evaluates every signal before it becomes an order (ADR-0006).
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    symbol: str
    kind: SignalType = SignalType.TARGET_WEIGHT
    weight: float | None = None  # fraction of NAV, in [-1, 1] for long/short
    quantity: float | None = None  # signed shares; + buy, - sell
    reason: str = ""  # human-readable rationale, surfaced in audit log

    @field_validator("symbol")
    @classmethod
    def _norm(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("weight")
    @classmethod
    def _weight_range(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not -1.0 <= v <= 1.0:
            raise ValueError(f"weight must be in [-1, 1], got {v}")
        return v

    @classmethod
    def target_weight(cls, symbol: str, weight: float, ts: datetime | None = None, reason: str = "") -> Signal:
        """Convenience constructor for a TARGET_WEIGHT signal."""
        return Signal(timestamp=ts or utcnow(), symbol=symbol, kind=SignalType.TARGET_WEIGHT,
                      weight=weight, reason=reason)

    @classmethod
    def delta_shares(cls, symbol: str, qty: float, ts: datetime | None = None, reason: str = "") -> Signal:
        """Convenience constructor for a DELTA_SHARES signal."""
        return Signal(timestamp=ts or utcnow(), symbol=symbol, kind=SignalType.DELTA_SHARES,
                      quantity=qty, reason=reason)


# ──────────────────────────────── Order ────────────────────────────────


class Order(BaseModel):
    """A concrete, broker-ready order request.

    ``quantity`` is signed: positive = buy, negative = sell. For limit/stop
    orders ``limit_price`` / ``stop_price`` must be set; validated per type.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    side: OrderSide
    quantity: float = Field(gt=0)  # magnitude, always positive
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    time_in_force: str = "day"
    created_at: datetime = Field(default_factory=utcnow)
    client_order_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def _norm(cls, v: str) -> str:
        return v.upper().strip()

    @model_validator(mode="after")
    def _conditional_prices(self) -> Order:
        """Ensure limit/stop orders carry the prices their type requires.

        Run in ``after`` mode so every field is already populated — a
        ``field_validator`` on ``order_type`` would fire before
        ``limit_price``/``stop_price`` are parsed and reject valid orders.
        """
        t = self.order_type
        if t in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.limit_price is None:
            raise ValueError(f"{t} order requires limit_price")
        if t in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError(f"{t} order requires stop_price")
        return self

    @property
    def signed_quantity(self) -> float:
        """Signed shares: + for buy, - for sell."""
        return self.quantity if self.side == OrderSide.BUY else -self.quantity


# ──────────────────────────────── Fill ────────────────────────────────


class Fill(BaseModel):
    """A realized execution. The source of truth for portfolio P&L."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    symbol: str
    side: OrderSide
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    commission: float = Field(ge=0)
    order_type: OrderType = OrderType.MARKET

    @property
    def signed_quantity(self) -> float:
        return self.quantity if self.side == OrderSide.BUY else -self.quantity

    @property
    def notional(self) -> float:
        return self.quantity * self.price

    @property
    def signed_notional(self) -> float:
        """Negative for sells — useful for cash accounting."""
        return self.signed_quantity * self.price

    @property
    def side_of_position(self) -> Side:
        """LONG if the fill increases a long (or opens via buy), else SHORT."""
        return Side.LONG if self.side == OrderSide.BUY else Side.SHORT


__all__ = [
    "Fill",
    "Order",
    "OrderStatus",
    "Signal",
    "SignalType",
]
