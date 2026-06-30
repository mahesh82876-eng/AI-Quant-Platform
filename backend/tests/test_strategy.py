"""Unit tests for strategies (quant.strategy) — the ADR-0007 contract.

Validates that strategies are pure mappings with no lookahead: Buy&Hold enters
once, MA-cross flips on a real crossover, and the deterministic Random
strategy is reproducible.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant.strategy import BuyAndHoldStrategy, MovingAverageCrossStrategy, RandomStrategy
from quant.types import Bar, BarSeries, MarketData

pytestmark = pytest.mark.unit


def _series(symbol: str, closes: list[float]) -> BarSeries:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [
        Bar(timestamp=t0 + timedelta(days=i), symbol=symbol, open=c, high=c + 1,
            low=max(0.01, c - 1), close=c, volume=1000)
        for i, c in enumerate(closes)
    ]
    return BarSeries(symbol=symbol, bars=bars)


def _data(symbol: str, closes: list[float]) -> MarketData:
    return MarketData().add(_series(symbol, closes))


# ---- Buy & Hold ----

def test_buy_and_hold_emits_once_then_silent():
    data = _data("AAPL", [100, 101, 102, 103, 104])
    s = BuyAndHoldStrategy("AAPL")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # bar 0
    sigs0 = s.on_bar(t0, data.slice_through(t0), _pf())
    assert len(sigs0) == 1
    assert sigs0[0].weight == 1.0
    # bar 1+ → no more signals
    sigs1 = s.on_bar(t0 + timedelta(days=1), data.slice_through(t0 + timedelta(days=1)), _pf())
    assert sigs1 == []


def test_buy_and_hold_respects_custom_weight():
    data = _data("AAPL", [100, 101])
    s = BuyAndHoldStrategy("AAPL", target_weight=0.5)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sigs = s.on_bar(t0, data.slice_through(t0), _pf())
    assert sigs[0].weight == 0.5


def test_buy_and_hold_silent_when_symbol_absent():
    s = BuyAndHoldStrategy("AAPL")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert s.on_bar(t0, MarketData(), _pf()) == []


# ---- MA Cross ----

def test_ma_cross_validates_fast_less_than_slow():
    with pytest.raises(ValueError):
        MovingAverageCrossStrategy("AAPL", fast=50, slow=20)


def test_ma_cross_emits_one_golden_cross_on_uptrend():
    # Monotonic uptrend → once both SMAs exist, fast > slow forever.
    data = _data("AAPL", [float(100 + i) for i in range(30)])
    s = MovingAverageCrossStrategy("AAPL", fast=5, slow=20)
    signals = []
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(30):
        ts = t0 + timedelta(days=i)
        signals.extend(s.on_bar(ts, data.slice_through(ts), _pf()))
    # Exactly one golden-cross entry (long), no death cross in a pure uptrend.
    assert len(signals) == 1
    assert signals[0].weight == 1.0


def test_ma_cross_flips_on_zigzag():
    # Build a clear up-then-down-then-up path so SMAs genuinely cross.
    closes = [100 + i for i in range(15)] + [114 - i for i in range(1, 15)]
    data = _data("AAPL", closes)
    s = MovingAverageCrossStrategy("AAPL", fast=3, slow=10)
    signals = []
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(len(closes)):
        ts = t0 + timedelta(days=i)
        signals.extend(s.on_bar(ts, data.slice_through(ts), _pf()))
    # Must see at least one flip to flat (death cross) after the reversal.
    weights = [sig.weight for sig in signals]
    assert 0.0 in weights  # went to cash at some point


# ---- Random (deterministic baseline) ----

def test_random_strategy_is_reproducible():
    data = _data("AAPL", [100, 101, 102, 103, 104])
    s1 = RandomStrategy(["AAPL"], seed=42)
    s2 = RandomStrategy(["AAPL"], seed=42)
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = s1.on_bar(t0, data.slice_through(t0), _pf())
    b = s2.on_bar(t0, data.slice_through(t0), _pf())
    assert [s.weight for s in a] == [s.weight for s in b]


def _pf():
    """Empty portfolio stand-in (strategies only read it here)."""
    from quant.portfolio import Portfolio

    return Portfolio(cash=100_000.0)
