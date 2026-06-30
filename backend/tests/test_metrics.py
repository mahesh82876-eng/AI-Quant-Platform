"""Unit tests for performance metrics (quant.metrics).

Validates the analytic functions against hand-computed expectations: returns
derivation, Sharpe sign/scale, drawdown peak-to-trough, VaR/CVaR tail
behavior, and the roll-up ``compute_metrics``.
"""

from __future__ import annotations

import math

import pytest

from quant.metrics import (
    annualized_return,
    annualized_volatility,
    compute_metrics,
    conditional_var,
    max_drawdown,
    profit_factor,
    returns_from_equity,
    sharpe_ratio,
    sortino_ratio,
    value_at_risk,
    win_rate,
)

pytestmark = pytest.mark.unit


def test_returns_from_equity_simple():
    # 100 → 110 → 99 : returns = +10%, -10%
    rets = returns_from_equity([100.0, 110.0, 99.0])
    assert rets == pytest.approx([0.10, -0.10])


def test_returns_from_equity_too_short():
    assert returns_from_equity([100.0]) == []
    assert returns_from_equity([]) == []


def test_sharpe_positive_for_consistent_gains():
    # Returns with a positive mean and real variance → positive Sharpe.
    rets = [0.001, 0.002, 0.0015, 0.0008, 0.0012, 0.0019, 0.0011, 0.0014]
    assert sharpe_ratio(rets) > 0


def test_sharpe_zero_on_flat():
    assert sharpe_ratio([0.0, 0.0, 0.0]) == 0.0


def test_sortino_inf_when_no_downside_and_positive_mean():
    assert math.isinf(sortino_ratio([0.01, 0.02, 0.03]))


def test_max_drawdown_identifies_trough():
    # peak 110 at idx1, trough 99 at idx2 → dd = (110-99)/110 = 0.1
    mdd, trough = max_drawdown([100.0, 110.0, 99.0, 105.0])
    assert mdd == pytest.approx((110.0 - 99.0) / 110.0, rel=1e-6)
    assert trough == 2


def test_max_drawdown_zero_on_monotonic_up():
    mdd, _ = max_drawdown([1.0, 2.0, 3.0, 4.0])
    assert mdd == 0.0


def test_value_at_risk_uses_historical_tail():
    rets = [-0.05, -0.02, 0.0, 0.01, 0.03]
    var = value_at_risk(rets, confidence=0.95)
    assert var > 0  # reports a loss magnitude
    assert var == pytest.approx(0.05)  # worst in the tail


def test_cvar_ge_var():
    rets = [-0.05, -0.02, 0.0, 0.01, 0.03]
    var = value_at_risk(rets)
    cvar = conditional_var(rets)
    assert cvar >= var  # expected shortfall ≥ VaR


def test_win_rate_and_profit_factor():
    trades = [10.0, -5.0, 20.0, -2.0]
    assert win_rate(trades) == 0.5
    # profit factor = (10+20) / (5+2) = 30/7
    assert profit_factor(trades) == pytest.approx(30.0 / 7.0)


def test_annualized_return_cagr_shape():
    # +100% total over 252 periods (1 yr) → +100% annualized
    assert annualized_return(1.0, 252) == pytest.approx(1.0)


def test_compute_metrics_rollup():
    equity = [100.0 * (1.001 ** i) for i in range(50)]
    m = compute_metrics(equity)
    assert m.total_return > 0
    assert m.sharpe > 0
    assert m.max_drawdown >= 0.0
    assert m.n_periods == 49
    assert m.final_equity == equity[-1]


def test_compute_metrics_empty_equity():
    m = compute_metrics([])
    assert m.total_return == 0.0
    assert m.n_periods == 0


def test_compute_metrics_with_trade_returns():
    m = compute_metrics([100.0, 110.0], trade_returns=[5.0, -2.0])
    assert "win_rate" in m.extra
    assert m.extra["win_rate"] == pytest.approx(0.5)


def test_annualized_volatility_positive():
    rets = [0.01, -0.01, 0.02, -0.005]
    assert annualized_volatility(rets) > 0
