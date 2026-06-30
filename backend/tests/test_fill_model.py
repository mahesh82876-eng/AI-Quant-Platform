"""Unit tests for the cost + fill models (quant.fill_model, ADR-0011).

Validates that realism is the default: every fill carries commission and
adverse slippage, and that idealized mode is the only zero-cost path.
Also covers the order-type fill rules (market/limit/stop/stop-limit).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quant.fill_model import (
    CostModel,
    DEFAULT_COSTS,
    IDEALIZED_COSTS,
    SimpleFillModel,
)
from quant.orders import Order, OrderSide, OrderType
from quant.types import Bar

pytestmark = pytest.mark.unit


def _bar(low: float = 99.0, high: float = 101.0, close: float = 100.0) -> Bar:
    return Bar(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), symbol="AAPL",
               open=100.0, high=high, low=low, close=close, volume=1000)


def _order(side: OrderSide = OrderSide.BUY, qty: float = 100,
           order_type: OrderType = OrderType.MARKET,
           limit_price: float | None = None, stop_price: float | None = None) -> Order:
    return Order(symbol="AAPL", side=side, quantity=qty, order_type=order_type,
                 limit_price=limit_price, stop_price=stop_price)


# ---- CostModel ----

def test_default_cost_applies_commission_and_slippage():
    cost = DEFAULT_COSTS
    comm = cost.commission(quantity=100, price=50.0)
    assert comm > 0
    # slippage is adverse: a positive fraction of price
    assert cost.slippage(100.0) == pytest.approx(100.0 * 5.0 / 10_000.0)


def test_idealized_cost_is_zero():
    cost = IDEALIZED_COSTS
    assert cost.commission(100, 50.0) == 0.0
    assert cost.slippage(100.0) == 0.0


def test_commission_respects_minimum():
    # tiny trade: per-share should be bumped to the minimum
    cost = CostModel(commission_per_share=0.005, commission_min=1.0)
    assert cost.commission(quantity=1, price=50.0) == pytest.approx(1.0)


# ---- SimpleFillModel ----

def test_market_buy_fills_at_close_plus_slippage():
    fills = SimpleFillModel().fill(_order(OrderSide.BUY), _bar(close=100.0), DEFAULT_COSTS)
    assert len(fills) == 1
    f = fills[0]
    assert f.price > 100.0  # buy pays above close (adverse)
    assert f.commission > 0


def test_market_sell_fills_at_close_minus_slippage():
    fills = SimpleFillModel().fill(_order(OrderSide.SELL), _bar(close=100.0), DEFAULT_COSTS)
    assert fills[0].price < 100.0  # sell receives below close (adverse)


def test_limit_buy_fills_only_if_bar_reaches_limit():
    # limit 99, bar traded 99..101 → fills at 99
    fills = SimpleFillModel().fill(
        _order(OrderSide.BUY, order_type=OrderType.LIMIT, limit_price=99.0),
        _bar(low=99.0, high=101.0), DEFAULT_COSTS)
    assert len(fills) == 1
    # limit 98, bar 99..101 → not filled
    no = SimpleFillModel().fill(
        _order(OrderSide.BUY, order_type=OrderType.LIMIT, limit_price=98.0),
        _bar(low=99.0, high=101.0), DEFAULT_COSTS)
    assert no == []


def test_stop_buy_triggers_when_high_reaches_stop():
    fills = SimpleFillModel().fill(
        _order(OrderSide.BUY, order_type=OrderType.STOP, stop_price=100.5),
        _bar(low=99.0, high=101.0), DEFAULT_COSTS)
    assert len(fills) == 1


def test_stop_does_not_trigger_untouched():
    no = SimpleFillModel().fill(
        _order(OrderSide.BUY, order_type=OrderType.STOP, stop_price=102.0),
        _bar(low=99.0, high=101.0), DEFAULT_COSTS)
    assert no == []


def test_stop_limit_requires_both_trigger_and_limit_reachable():
    fills = SimpleFillModel().fill(
        _order(OrderSide.BUY, order_type=OrderType.STOP_LIMIT, stop_price=100.5, limit_price=101.0),
        _bar(low=99.0, high=101.5), DEFAULT_COSTS)
    assert len(fills) == 1


def test_idealized_backtest_has_zero_costs_on_fill():
    fills = SimpleFillModel().fill(_order(OrderSide.BUY), _bar(close=100.0), IDEALIZED_COSTS)
    assert fills[0].commission == 0.0
    assert fills[0].price == 100.0  # no slippage
