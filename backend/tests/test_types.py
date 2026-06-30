"""Unit tests for domain value objects (quant.types).

Pure, no infrastructure. Validates the invariants that the engines rely on:
OHLCV consistency, strict-ascending bars, instrument normalization, and the
no-lookahead slicing semantics (slice_until / slice_through).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant.types import AssetClass, Bar, BarSeries, Instrument, MarketData

pytestmark = pytest.mark.unit


def _bar(ts: datetime, close: float = 100.0, symbol: str = "AAPL") -> Bar:
    return Bar(timestamp=ts, symbol=symbol, open=close, high=close + 1, low=close - 1,
               close=close, volume=1000)


# ---- Instrument ----

def test_instrument_normalizes_symbol():
    inst = Instrument(symbol="aapl")
    assert inst.symbol == "AAPL"
    assert inst.asset_class == AssetClass.EQUITY


def test_instrument_rejects_empty_symbol():
    with pytest.raises(Exception):
        Instrument(symbol="")


def test_instrument_frozen():
    inst = Instrument(symbol="AAPL")
    with pytest.raises(Exception):
        inst.symbol = "MSFT"  # type: ignore[misc]


# ---- Bar invariants ----

def test_bar_rejects_high_below_open():
    with pytest.raises(Exception):
        Bar(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), symbol="AAPL",
            open=100, high=99, low=98, close=100, volume=1)


def test_bar_rejects_close_above_high():
    with pytest.raises(Exception):
        Bar(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), symbol="AAPL",
            open=100, high=101, low=99, close=102, volume=1)


def test_bar_rejects_zero_price():
    with pytest.raises(Exception):
        Bar(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), symbol="AAPL",
            open=0, high=1, low=0, close=1, volume=1)


# ---- BarSeries ----

def test_barseries_must_be_strictly_ascending():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = t0 + timedelta(days=1)
    with pytest.raises(Exception):
        BarSeries(symbol="AAPL", bars=[_bar(t1), _bar(t0)])  # reversed


def test_barseries_slice_until_is_strict_exclusive():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(t0 + timedelta(days=i)) for i in range(5)]
    s = BarSeries(symbol="AAPL", bars=bars)
    # slice_until(day2) includes only day0, day1 (strict < day2)
    assert len(s.slice_until(t0 + timedelta(days=2))) == 2


def test_barseries_slice_through_is_inclusive():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(t0 + timedelta(days=i)) for i in range(5)]
    s = BarSeries(symbol="AAPL", bars=bars)
    # slice_through(day2) includes day0, day1, day2 (<= day2)
    assert len(s.slice_through(t0 + timedelta(days=2))) == 3
    # First bar is now visible to the backtest (the bug fix)
    assert len(s.slice_through(t0)) == 1


def test_barseries_closes_and_timestamps():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(t0 + timedelta(days=i), close=100.0 + i) for i in range(3)]
    s = BarSeries(symbol="AAPL", bars=bars)
    assert s.closes == [100.0, 101.0, 102.0]
    assert len(s.timestamps) == 3


# ---- MarketData ----

def test_marketdata_immutable_add():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(t0 + timedelta(days=i), symbol="AAPL") for i in range(3)]
    md = MarketData().add(BarSeries(symbol="AAPL", bars=bars))
    assert "AAPL" in md.symbols
    assert md.get("AAPL") is not None
    assert md.get("MSFT") is None


def test_marketdata_slice_until_no_lookahead():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(t0 + timedelta(days=i), symbol="AAPL") for i in range(5)]
    md = MarketData().add(BarSeries(symbol="AAPL", bars=bars))
    # At day2 we must NOT see day3
    visible = md.slice_until(t0 + timedelta(days=3))
    visible_bars = visible.get("AAPL")
    assert visible_bars is not None
    assert all(b.timestamp < t0 + timedelta(days=3) for b in visible_bars)
