"""Unit tests for the portfolio accounting layer (quant.portfolio).

Validates average-cost position accounting, realized P&L on reductions/flips,
cash impact of fills, and mark-to-market valuation. These are the invariants
that make the backtest's equity curve trustworthy.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant.orders import Fill, OrderSide
from quant.portfolio import Portfolio, Position
from quant.types import Side

pytestmark = pytest.mark.unit


def _fill(symbol: str, side: OrderSide, qty: float, price: float, comm: float = 1.0) -> Fill:
    return Fill(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), symbol=symbol,
                side=side, quantity=qty, price=price, commission=comm)


# ---- Position accounting ----

def test_position_opens_long_on_buy():
    p = Position(symbol="AAPL")
    p.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0))
    assert p.quantity == 100
    assert p.avg_cost == 50.0
    assert p.side == Side.LONG
    assert p.is_flat is False


def test_position_avg_cost_on_multiple_buys():
    p = Position(symbol="AAPL")
    p.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0))
    p.apply(_fill("AAPL", OrderSide.BUY, 100, 60.0))
    # weighted avg = (100*50 + 100*60) / 200 = 55
    assert p.avg_cost == pytest.approx(55.0)
    assert p.quantity == 200


def test_position_realizes_pnl_on_reduction():
    p = Position(symbol="AAPL")
    p.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0))
    # sell 50 @ 60 → realize 50 * (60-50) = 500
    p.apply(_fill("AAPL", OrderSide.SELL, 50, 60.0))
    assert p.quantity == 50
    assert p.realized_pnl == pytest.approx(500.0)


def test_position_flips_long_to_short_realizes_full_pnl():
    p = Position(symbol="AAPL")
    p.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0))
    # sell 200 @ 60 → close 100 long (realize 100*10=1000), open 100 short @ 60
    p.apply(_fill("AAPL", OrderSide.SELL, 200, 60.0))
    assert p.quantity == -100
    assert p.side == Side.SHORT
    assert p.realized_pnl == pytest.approx(1000.0)
    assert p.avg_cost == pytest.approx(60.0)


def test_position_goes_flat_resets_cost():
    p = Position(symbol="AAPL")
    p.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0))
    p.apply(_fill("AAPL", OrderSide.SELL, 100, 55.0))
    assert p.is_flat
    assert p.avg_cost == 0.0
    assert p.realized_pnl == pytest.approx(500.0)


def test_position_mtm_and_unrealized():
    p = Position(symbol="AAPL")
    p.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0))
    assert p.market_value(60.0) == pytest.approx(6000.0)
    assert p.unrealized_pnl(60.0) == pytest.approx(1000.0)


# ---- Portfolio accounting ----

def test_portfolio_buy_decreases_cash_by_notional_plus_commission():
    pf = Portfolio(cash=10_000.0)
    pf.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0, comm=5.0))
    # cash = 10000 - (100*50) - 5 = 4995
    assert pf.cash == pytest.approx(4995.0)
    assert pf.position("AAPL").quantity == 100


def test_portfolio_total_equity_closes_back_to_initial_at_entry_price():
    pf = Portfolio(cash=10_000.0)
    pf.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0, comm=0.0))
    # no price move + no commission → equity unchanged
    assert pf.total_equity({"AAPL": 50.0}) == pytest.approx(10_000.0)


def test_portfolio_total_equity_tracks_price():
    pf = Portfolio(cash=10_000.0)
    pf.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0, comm=0.0))
    assert pf.total_equity({"AAPL": 60.0}) == pytest.approx(11_000.0)


def test_portfolio_exposures_as_fraction_of_nav():
    pf = Portfolio(cash=10_000.0)
    pf.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0, comm=0.0))
    # Buy 5000 of stock from 10000 cash → 5000 cash + 5000 stock = 10000 equity;
    # exposure = 5000 / 10000 = 0.5
    snap = pf.snapshot({"AAPL": 50.0})
    assert snap.gross_exposure == pytest.approx(0.5)
    assert snap.net_exposure == pytest.approx(0.5)


def test_portfolio_symbols_excludes_flat():
    pf = Portfolio(cash=10_000.0)
    pf.apply(_fill("AAPL", OrderSide.BUY, 100, 50.0))
    pf.apply(_fill("AAPL", OrderSide.SELL, 100, 50.0))
    assert "AAPL" not in pf.symbols


def test_portfolio_rejects_wrong_symbol_fill():
    pf = Portfolio(cash=10_000.0)
    with pytest.raises(ValueError):
        pf.position("AAPL").apply(_fill("MSFT", OrderSide.BUY, 10, 50.0))
