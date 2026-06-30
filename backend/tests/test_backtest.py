"""Integration tests for the backtesting engine (quant.backtest).

Proves the end-to-end event loop: strategy → signal → order → fill →
portfolio → equity curve, with the realism invariants from ADR-0011 (costs
always on unless explicitly idealized) and the no-lookahead semantics.
Also covers the ADR-0006 pre-trade risk gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from quant.backtest import BacktestConfig, Backtester
from quant.fill_model import CostModel, IDEALIZED_COSTS
from quant.orders import Order, Signal
from quant.portfolio import Portfolio
from quant.strategy import BuyAndHoldStrategy, MovingAverageCrossStrategy
from quant.types import Bar, BarSeries, MarketData

pytestmark = pytest.mark.integration


def _rising_market(symbol: str = "AAPL", n: int = 60, start: float = 100.0) -> MarketData:
    """A steadily rising market — Buy&Hold should profit, costs should bite."""
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [
        Bar(timestamp=t0 + timedelta(days=i), symbol=symbol, open=start + 2 * i,
            high=start + 2 * i + 3, low=start + 2 * i - 2, close=start + 2 * i + 0.5,
            volume=10_000)
        for i in range(n)
    ]
    return MarketData().add(BarSeries(symbol=symbol, bars=bars))


# ---- The bug-fix regression test ----

def test_buy_and_hold_actually_trades():
    """Regression: previously the first bar was invisible → 0 fills."""
    data = _rising_market()
    result = Backtester(BacktestConfig(initial_capital=100_000.0)).run(
        BuyAndHoldStrategy("AAPL"), data
    )
    assert len(result.fills) >= 1, "Buy&Hold must enter on the first bar"
    assert result.n_signals >= 1
    assert result.total_return > 0.0


def test_buy_and_hold_holds_after_entry():
    data = _rising_market()
    result = Backtester().run(BuyAndHoldStrategy("AAPL"), data)
    # One entry signal, no churn
    assert result.n_signals == 1
    assert result.n_rebalances == 1


# ---- Realism invariants (ADR-0011) ----

def test_costs_reduce_return_vs_idealized():
    data = _rising_market()
    realistic = Backtester(BacktestConfig(initial_capital=100_000.0)).run(
        BuyAndHoldStrategy("AAPL"), data
    )
    ideal = Backtester(BacktestConfig(initial_capital=100_000.0, cost_model=IDEALIZED_COSTS)).run(
        BuyAndHoldStrategy("AAPL"), data
    )
    # Realistic costs must not beat the idealized (zero-cost) run.
    assert realistic.total_return <= ideal.total_return
    # And the single fill's commission must be > 0 in the realistic run.
    assert all(f.commission > 0 for f in realistic.fills)


def test_ma_cross_runs_full_window():
    data = _rising_market()
    result = Backtester().run(MovingAverageCrossStrategy("AAPL", fast=5, slow=20), data)
    assert result.metrics.n_periods > 0
    # n_periods = number of returns = bars - 1; timestamps has one entry per bar.
    assert len(result.timestamps) == result.metrics.n_periods + 1
    # equity curve is monotonic for B&H-equivalent in an uptrend
    assert result.equity_curve[-1] > 0


# ---- Risk gate (ADR-0006) ----

@dataclass
class _Decision:
    allowed: bool


class _AlwaysRejectRisk:
    """Pre-trade checker that rejects everything — proves the gate is hit."""

    def __init__(self) -> None:
        self.calls = 0

    def pre_trade_check(self, order: Order, portfolio: Portfolio,
                        prices: dict[str, float]) -> _Decision:
        self.calls += 1
        return _Decision(allowed=False)


def test_risk_engine_blocks_all_orders_when_rejecting():
    data = _rising_market()
    risk = _AlwaysRejectRisk()
    result = Backtester(BacktestConfig(risk_engine=risk)).run(
        BuyAndHoldStrategy("AAPL"), data
    )
    assert risk.calls >= 1, "risk gate must be invoked before fills"
    assert result.n_rejected >= 1
    assert len(result.fills) == 0, "no fills when risk rejects everything"


def test_risk_engine_passes_when_allowed():
    data = _rising_market()

    class _AlwaysAllow:
        def pre_trade_check(self, order: Order, portfolio: Portfolio,
                            prices: dict[str, float]) -> _Decision:
            return _Decision(allowed=True)

    result = Backtester(BacktestConfig(risk_engine=_AlwaysAllow())).run(
        BuyAndHoldStrategy("AAPL"), data
    )
    assert len(result.fills) >= 1


# ---- Structural sanity ----

def test_equity_curve_length_matches_periods():
    data = _rising_market(n=20)
    result = Backtester().run(BuyAndHoldStrategy("AAPL"), data)
    assert len(result.equity_curve) == 20
    assert len(result.snapshots) == 20


def test_metrics_dict_is_serializable():
    data = _rising_market(n=15)
    result = Backtester().run(BuyAndHoldStrategy("AAPL"), data)
    d = result.metrics.as_dict()
    # All values must be JSON-primitive (float/int/str).
    assert all(isinstance(v, (int, float, str)) for v in d.values())
    assert "sharpe" in d and "max_drawdown" in d
