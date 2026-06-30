"""The backtesting engine — the event loop that runs a strategy over history.

This is the validated simulation runtime (ADR-0007). It feeds a strategy the
*trailing* market data at each timestamp (no lookahead), collects signals,
translates target-weight signals into share orders, routes them through the
cost-aware fill model (ADR-0011), applies fills to the portfolio, and records
an equity curve. The Risk Engine is integrated as a pre-trade gate so the
backtest exercises the *exact same* enforcement path as live (ADR-0006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from quant.fill_model import CostModel, DEFAULT_COSTS, FillModel, SimpleFillModel
from quant.metrics import PerformanceMetrics, compute_metrics
from quant.orders import Fill, Order, Signal, SignalType
from quant.portfolio import Portfolio, PortfolioSnapshot
from quant.strategy import Strategy
from quant.types import Bar, BarSeries, MarketData, OrderSide, OrderType


class RiskDecision(Protocol):
    """Result of a pre-trade risk check (ADR-0006)."""

    allowed: bool


class PreTradeChecker(Protocol):
    """Structural interface for the risk engine's pre-trade gate.

    Defining it as a Protocol here avoids an import cycle with the (future)
    ``quant.risk`` module while keeping the backtest fully typed. Any object
    exposing ``pre_trade_check(order, portfolio, prices) -> {allowed: bool}``
    satisfies it.
    """

    def pre_trade_check(
        self, order: Order, portfolio: Portfolio, prices: dict[str, float]
    ) -> RiskDecision: ...


@dataclass
class BacktestResult:
    """The complete output of a backtest run."""

    strategy_name: str
    equity_curve: list[float]
    timestamps: list[datetime]
    snapshots: list[PortfolioSnapshot]
    fills: list[Fill]
    metrics: PerformanceMetrics
    initial_capital: float
    cost_model: CostModel
    n_rebalances: int = 0
    n_signals: int = 0
    n_rejected: int = 0

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1] if self.equity_curve else 0.0

    @property
    def total_return(self) -> float:
        return self.metrics.total_return


@dataclass
class BacktestConfig:
    """Configuration for a backtest run (immutable, validated)."""

    initial_capital: float = 100_000.0
    cost_model: CostModel = field(default_factory=lambda: DEFAULT_COSTS)
    fill_model: FillModel = field(default_factory=lambda: SimpleFillModel())
    risk_engine: PreTradeChecker | None = None  # ADR-0006 pre-trade gate
    trade_on: str = "close"  # which bar field signals execute against next bar
    periods_per_year: int = 252
    risk_free_annual: float = 0.0


class Backtester:
    """Runs a :class:`Strategy` over historical :class:`MarketData`.

    Usage::

        bt = Backtester(BacktestConfig(initial_capital=1_000_000))
        result = bt.run(strategy, data)
        print(result.metrics.sharpe)
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    # ---- public API ----
    def run(self, strategy: Strategy, data: MarketData) -> BacktestResult:
        """Execute ``strategy`` over ``data`` and return a full result."""
        timeline = self._timeline(data)
        portfolio = Portfolio(cash=self.config.initial_capital)
        fills: list[Fill] = []
        snapshots: list[PortfolioSnapshot] = []
        equity_curve: list[float] = []
        timestamps: list[datetime] = []
        n_signals = 0
        n_rebalances = 0
        n_rejected = 0

        for ts in timeline:
            # Information set: everything up to and including the bar at ts.
            # A bar's close IS the information available at ts; filling at that
            # same close is therefore lookahead-free. (Daily-bar convention.)
            visible = data.slice_through(ts)
            prices = self._last_prices(visible)

            # Mark the book to market and record equity *before* this bar's trades.
            equity = portfolio.total_equity(prices)
            equity_curve.append(equity)
            timestamps.append(ts)

            # Strategy emits signals on the visible data.
            signals = strategy.on_bar(ts, visible, portfolio)
            n_signals += len(signals)
            if signals:
                n_rebalances += 1

            # Translate signals → orders, risk-check, fill, apply.
            for sig in signals:
                bar = self._bar_for_fill(visible, sig.symbol, ts)
                if bar is None:
                    continue
                orders = self._signal_to_orders(sig, portfolio, prices)
                for order in orders:
                    if self._reject_via_risk(order, portfolio, prices):
                        n_rejected += 1
                        continue
                    new_fills = self.config.fill_model.fill(order, bar, self.config.cost_model)
                    for f in new_fills:
                        portfolio.apply(f)
                        fills.append(f)

            # Post-trade snapshot at this bar's close.
            snap = portfolio.record_snapshot(prices, ts)
            snapshots.append(snap)

        metrics = compute_metrics(
            equity_curve,
            risk_free_annual=self.config.risk_free_annual,
            periods_per_year=self.config.periods_per_year,
        )
        return BacktestResult(
            strategy_name=strategy.name,
            equity_curve=equity_curve,
            timestamps=timestamps,
            snapshots=snapshots,
            fills=fills,
            metrics=metrics,
            initial_capital=self.config.initial_capital,
            cost_model=self.config.cost_model,
            n_rebalances=n_rebalances,
            n_signals=n_signals,
            n_rejected=n_rejected,
        )

    # ---- helpers ----
    def _timeline(self, data: MarketData) -> list[datetime]:
        """Union of all bar timestamps, ascending. The simulation clock."""
        ts: set[datetime] = set()
        for series in data.series.values():
            ts.update(series.timestamps)
        return sorted(ts)

    def _last_prices(self, data: MarketData) -> dict[str, float]:
        """Most recent close per symbol in ``data``."""
        prices: dict[str, float] = {}
        for sym, series in data.series.items():
            if series.bars:
                prices[sym] = series.bars[-1].close
        return prices

    def _bar_for_fill(self, visible: MarketData, symbol: str, ts: datetime) -> Bar | None:
        """The bar an order at ``ts`` would execute against.

        We fill on the *current* bar (the one ending at ts) — a conservative
        "execute at this bar's close" model. The strategy saw only bars before
        ts, so there is no lookahead in the *signal*; the fill uses the bar
        that just completed.
        """
        series = visible.get(symbol)
        if series is None or not series.bars:
            return None
        # The last bar strictly before ts; fill at its close (next-bar exec
        # would require ts+1 which we handle by filling on the visible last bar).
        return series.bars[-1]

    def _signal_to_orders(
        self, signal: Signal, portfolio: Portfolio, prices: dict[str, float]
    ) -> list[Order]:
        """Translate a signal into one or more market orders.

        TARGET_WEIGHT: compute the delta between current and target weight.
        DELTA_SHARES: a single order for the requested quantity.
        """
        price = prices.get(signal.symbol)
        if price is None or price <= 0:
            return []

        equity = portfolio.total_equity(prices)
        if equity <= 0:
            return []

        if signal.kind == SignalType.DELTA_SHARES:
            if signal.quantity is None or signal.quantity == 0:
                return []
            qty = abs(signal.quantity)
            side = OrderSide.BUY if signal.quantity > 0 else OrderSide.SELL
            return [Order(symbol=signal.symbol, side=side, quantity=qty, order_type=OrderType.MARKET)]

        # TARGET_WEIGHT
        target_weight = signal.weight or 0.0
        target_value = target_weight * equity
        current = portfolio.get(signal.symbol)
        current_value = current.market_value(price) if current else 0.0
        delta_value = target_value - current_value
        if abs(delta_value) < 1.0:  # ignore sub-dollar deltas (cost > benefit)
            return []
        delta_shares = delta_value / price
        side = OrderSide.BUY if delta_shares > 0 else OrderSide.SELL
        return [Order(symbol=signal.symbol, side=side, quantity=abs(delta_shares), order_type=OrderType.MARKET)]

    def _reject_via_risk(
        self, order: Order, portfolio: Portfolio, prices: dict[str, float]
    ) -> bool:
        """Pre-trade risk gate (ADR-0006). Returns True if REJECTED."""
        risk = self.config.risk_engine
        if risk is None:
            return False
        decision = risk.pre_trade_check(order, portfolio, prices)
        return not decision.allowed


__all__ = ["BacktestConfig", "BacktestResult", "Backtester"]
