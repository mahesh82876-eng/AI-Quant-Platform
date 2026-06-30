"""Unit tests for the action layer (quant.orders): Signal, Order, Fill.

Validates the contracts the engines depend on: weight clamping, conditional
pricing for limit/stop orders, signed-quantity accounting, and notional math.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant.orders import Fill, Order, OrderSide, OrderType, Signal, SignalType

pytestmark = pytest.mark.unit


# ---- Signal ----

def test_signal_normalizes_symbol():
    s = Signal.target_weight("msft", 0.5)
    assert s.symbol == "MSFT"
    assert s.kind == SignalType.TARGET_WEIGHT


def test_signal_rejects_weight_out_of_range():
    with pytest.raises(Exception):
        Signal.target_weight("AAPL", 1.5)
    with pytest.raises(Exception):
        Signal.target_weight("AAPL", -1.5)


def test_signal_weight_zero_is_valid_cash_signal():
    s = Signal.target_weight("AAPL", 0.0, reason="go_to_cash")
    assert s.weight == 0.0


def test_delta_shares_signal_signed():
    s = Signal.delta_shares("AAPL", -100)
    assert s.kind == SignalType.DELTA_SHARES
    assert s.quantity == -100


# ---- Order ----

def test_market_order_signed_quantity():
    o = Order(symbol="AAPL", side=OrderSide.BUY, quantity=100)
    assert o.signed_quantity == 100
    o2 = Order(symbol="AAPL", side=OrderSide.SELL, quantity=100)
    assert o2.signed_quantity == -100


def test_limit_order_requires_limit_price():
    with pytest.raises(Exception):
        Order(symbol="AAPL", side=OrderSide.BUY, quantity=10, order_type=OrderType.LIMIT)
    # valid
    o = Order(symbol="AAPL", side=OrderSide.BUY, quantity=10,
              order_type=OrderType.LIMIT, limit_price=150.0)
    assert o.limit_price == 150.0


def test_stop_order_requires_stop_price():
    with pytest.raises(Exception):
        Order(symbol="AAPL", side=OrderSide.SELL, quantity=10, order_type=OrderType.STOP)
    o = Order(symbol="AAPL", side=OrderSide.SELL, quantity=10,
              order_type=OrderType.STOP, stop_price=140.0)
    assert o.stop_price == 140.0


def test_stop_limit_requires_both_prices():
    with pytest.raises(Exception):
        Order(symbol="AAPL", side=OrderSide.BUY, quantity=10, order_type=OrderType.STOP_LIMIT,
              stop_price=140.0)
    o = Order(symbol="AAPL", side=OrderSide.BUY, quantity=10, order_type=OrderType.STOP_LIMIT,
              stop_price=140.0, limit_price=141.0)
    assert o.stop_price == 140.0 and o.limit_price == 141.0


def test_order_normalizes_symbol():
    o = Order(symbol="aapl", side=OrderSide.BUY, quantity=1)
    assert o.symbol == "AAPL"


# ---- Fill ----

def test_fill_signed_quantities_and_notional():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    buy = Fill(timestamp=ts, symbol="AAPL", side=OrderSide.BUY, quantity=100, price=50.0,
               commission=1.0)
    assert buy.signed_quantity == 100
    assert buy.notional == 5000.0
    assert buy.signed_notional == 5000.0  # buy spends cash

    sell = Fill(timestamp=ts, symbol="AAPL", side=OrderSide.SELL, quantity=100, price=50.0,
                commission=1.0)
    assert sell.signed_notional == -5000.0  # sell receives cash


def test_fill_rejects_nonpositive_price():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(Exception):
        Fill(timestamp=ts, symbol="AAPL", side=OrderSide.BUY, quantity=100, price=0.0, commission=0)
