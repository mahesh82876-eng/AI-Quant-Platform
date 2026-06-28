"""Portfolio and position state.

A :class:`Portfolio` is the mutable book: cash + positions, valued against
current market prices. It is the single source of truth for "what do we
hold right now" and is updated only by applying :class:`~quant.orders.Fill`
objects. This is pure accounting — no strategy or risk logic here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from quant.orders import Fill
from quant.types import Side, utcnow


@dataclass
class Position:
    """A single long or short position in one symbol.

    Cost basis is average-cost. Short positions have negative shares and
    negative cost basis (proceeds from the short sale). MTM is computed
    against an externally-supplied price.
    """

    symbol: str
    quantity: float = 0.0  # signed: + long, - short
    avg_cost: float = 0.0  # average cost per share (signed like quantity)
    realized_pnl: float = 0.0

    @property
    def side(self) -> Side | None:
        if self.quantity > 1e-9:
            return Side.LONG
        if self.quantity < -1e-9:
            return Side.SHORT
        return None

    @property
    def is_flat(self) -> bool:
        return abs(self.quantity) < 1e-9

    @property
    def cost_basis(self) -> float:
        """Total cost of the current position (signed)."""
        return self.quantity * self.avg_cost

    def market_value(self, price: float) -> float:
        """Mark-to-market value of the position at ``price``."""
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        if self.is_flat:
            return 0.0
        return self.market_value(price) - self.cost_basis

    def apply(self, fill: Fill) -> None:
        """Update this position for a realized fill (average-cost accounting)."""
        if fill.symbol != self.symbol:
            raise ValueError(f"fill symbol {fill.symbol} != position symbol {self.symbol}")

        signed_qty = fill.signed_quantity
        new_quantity = self.quantity + signed_qty

        # Realize P&L when reducing or flipping a position.
        if self.quantity != 0.0 and ((self.quantity > 0) != (signed_qty > 0)):
            closing_qty = min(abs(signed_qty), abs(self.quantity))
            if self.quantity > 0:  # long being reduced
                self.realized_pnl += closing_qty * (fill.price - self.avg_cost)
            else:  # short being reduced
                self.realized_pnl += closing_qty * (self.avg_cost - fill.price)

        # Update average cost on the residual position (skip flips' cross-over).
        if (new_quantity > 0 and self.quantity >= 0) or (new_quantity < 0 and self.quantity <= 0):
            if abs(new_quantity) > 1e-9:
                self.avg_cost = (
                    (self.cost_basis + signed_qty * fill.price) / new_quantity
                )
        # On a flip (long→short or short→long), reset cost to the fill price.
        elif not (self.quantity == 0.0 and signed_qty == 0.0):
            self.avg_cost = fill.price if abs(new_quantity) > 1e-9 else 0.0

        self.quantity = new_quantity if abs(new_quantity) > 1e-9 else 0.0
        if self.is_flat:
            self.avg_cost = 0.0


@dataclass
class Portfolio:
    """The book: cash plus positions, valued against market prices.

    Immutable *except* through :meth:`apply` (fills) and :meth:`record_cash`.
    Never construct positions directly outside this class.
    """

    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    base_currency: str = "USD"
    history: list[PortfolioSnapshot] = field(default_factory=list)

    # ---- accessors ----
    def position(self, symbol: str) -> Position:
        return self.positions.setdefault(symbol, Position(symbol=symbol.upper()))

    def get(self, symbol: str) -> Position | None:
        return self.positions.get(symbol.upper())

    @property
    def symbols(self) -> list[str]:
        return [s for s, p in self.positions.items() if not p.is_flat]

    # ---- mutation ----
    def apply(self, fill: Fill) -> None:
        """Apply a fill: update the position and cash (commission + notional)."""
        pos = self.position(fill.symbol)
        pos.apply(fill)
        # Cash: pay/receive notional, always pay commission.
        self.cash -= fill.signed_notional + fill.commission

    def record_snapshot(self, prices: dict[str, float], ts: datetime | None = None) -> PortfolioSnapshot:
        """Mark the book to market and append a snapshot to history."""
        snap = self.snapshot(prices, ts)
        self.history.append(snap)
        return snap

    # ---- valuation ----
    def positions_value(self, prices: dict[str, float]) -> float:
        return sum(p.market_value(prices[s]) for s, p in self.positions.items() if s in prices)

    def total_equity(self, prices: dict[str, float]) -> float:
        return self.cash + self.positions_value(prices)

    def realized_pnl(self) -> float:
        return sum(p.realized_pnl for p in self.positions.values())

    def unrealized_pnl(self, prices: dict[str, float]) -> float:
        return sum(
            p.unrealized_pnl(prices[s]) for s, p in self.positions.items() if s in prices
        )

    def snapshot(self, prices: dict[str, float], ts: datetime | None = None) -> PortfolioSnapshot:
        """A point-in-time mark-to-market snapshot (does not append to history)."""
        equity = self.total_equity(prices)
        gross = sum(abs(p.market_value(prices[s])) for s, p in self.positions.items() if s in prices)
        net = self.positions_value(prices)
        return PortfolioSnapshot(
            timestamp=ts or utcnow(),
            cash=self.cash,
            positions_value=net,
            total_equity=equity,
            gross_exposure=(gross / equity) if equity > 0 else 0.0,
            net_exposure=(net / equity) if equity > 0 else 0.0,
            n_positions=len(self.symbols),
        )


@dataclass
class PortfolioSnapshot:
    """Immutable point-in-time portfolio state — one row of an equity curve."""

    timestamp: datetime
    cash: float
    positions_value: float
    total_equity: float
    gross_exposure: float  # fraction of NAV
    net_exposure: float  # fraction of NAV
    n_positions: int
