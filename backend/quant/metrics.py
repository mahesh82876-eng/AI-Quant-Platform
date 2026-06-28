"""Performance metrics for backtests and live portfolios.

All functions here are pure: equity series in → metrics out. They use only
the stdlib so the domain stays light; NumPy is used only where it materially
simplifies (annualization helpers). Annualization defaults assume 252 trading
days; override ``periods_per_year`` for intraday data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean, stdev

# ──────────────────────────────── Equity-curve metrics ─────────────────────


def returns_from_equity(equity: list[float]) -> list[float]:
    """Simple period returns from an equity curve. Returns len = len-1."""
    if len(equity) < 2:
        return []
    out = []
    for prev, cur in zip(equity, equity[1:], strict=False):
        if prev == 0:
            out.append(0.0)
        else:
            out.append(cur / prev - 1.0)
    return out


def annualized_return(total_return: float, n_periods: int, periods_per_year: int = 252) -> float:
    """Compound the total return to an annual figure (CAGR-style)."""
    if n_periods <= 0 or total_return <= -1.0:
        return 0.0
    years = n_periods / periods_per_year
    return (1.0 + total_return) ** (1.0 / years) - 1.0


def annualized_volatility(returns: list[float], periods_per_year: int = 252) -> float:
    if len(returns) < 2:
        return 0.0
    sd = stdev(returns)
    return sd * math.sqrt(periods_per_year)


def sharpe_ratio(returns: list[float], risk_free_annual: float = 0.0, periods_per_year: int = 252) -> float:
    """Annualized Sharpe. ``risk_free_annual`` is the annual risk-free rate."""
    if len(returns) < 2:
        return 0.0
    rf_per_period = (1.0 + risk_free_annual) ** (1.0 / periods_per_year) - 1.0
    excess = [r - rf_per_period for r in returns]
    sd = stdev(excess)
    if sd == 0:
        return 0.0
    return (mean(excess) / sd) * math.sqrt(periods_per_year)


def sortino_ratio(returns: list[float], risk_free_annual: float = 0.0, periods_per_year: int = 252) -> float:
    """Annualized Sortino — penalizes only downside deviation."""
    if len(returns) < 2:
        return 0.0
    rf_per_period = (1.0 + risk_free_annual) ** (1.0 / periods_per_year) - 1.0
    excess = [r - rf_per_period for r in returns]
    downside = [e for e in excess if e < 0]
    if not downside:
        return float("inf") if mean(excess) > 0 else 0.0
    dd_dev = math.sqrt(sum(e * e for e in downside) / len(downside))
    if dd_dev == 0:
        return 0.0
    return (mean(excess) / dd_dev) * math.sqrt(periods_per_year)


def max_drawdown(equity: list[float]) -> tuple[float, int]:
    """Peak-to-trough drawdown and the index of the trough.

    Returns ``(max_dd_fraction, trough_index)``. 0.0 = no drawdown.
    """
    if len(equity) < 2:
        return 0.0, 0
    peak = equity[0]
    max_dd = 0.0
    trough_idx = 0
    for i, v in enumerate(equity):
        if v > peak:
            peak = v
        if peak > 0:
            dd = peak - v
            frac = dd / peak
            if frac > max_dd:
                max_dd = frac
                trough_idx = i
    return max_dd, trough_idx


def calmar_ratio(total_return: float, n_periods: int, mdd: float, periods_per_year: int = 252) -> float:
    """Annualized return / max drawdown."""
    if mdd <= 0:
        return float("inf") if total_return > 0 else 0.0
    ann = annualized_return(total_return, n_periods, periods_per_year)
    return ann / mdd


def downside_deviation(returns: list[float], periods_per_year: int = 252) -> float:
    downside = [min(0.0, r) for r in returns]
    if not downside:
        return 0.0
    return math.sqrt(sum(d * d for d in downside) / len(downside)) * math.sqrt(periods_per_year)


def win_rate(trade_returns: list[float]) -> float:
    if not trade_returns:
        return 0.0
    wins = sum(1 for r in trade_returns if r > 0)
    return wins / len(trade_returns)


def profit_factor(trade_returns: list[float]) -> float:
    gross_profit = sum(r for r in trade_returns if r > 0)
    gross_loss = -sum(r for r in trade_returns if r < 0)
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def value_at_risk(returns: list[float], confidence: float = 0.95) -> float:
    """Historical VaR as a positive loss fraction (e.g., 0.03 = 3% loss)."""
    if not returns:
        return 0.0
    sorted_r = sorted(returns)
    idx = max(0, int((1.0 - confidence) * len(sorted_r)) - 1)
    return -sorted_r[idx]


def conditional_var(returns: list[float], confidence: float = 0.95) -> float:
    """Expected shortfall: average loss in the worst (1-c) tail."""
    if not returns:
        return 0.0
    sorted_r = sorted(returns)
    cutoff = max(1, int((1.0 - confidence) * len(sorted_r)))
    tail = sorted_r[:cutoff]
    return -mean(tail)


# ──────────────────────────────── Roll-up ────────────────────────────────


@dataclass
class PerformanceMetrics:
    """One-stop performance summary for an equity curve."""

    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    n_periods: int
    final_equity: float
    initial_equity: float
    extra: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float | int | str]:
        d = {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "annualized_volatility": self.annualized_volatility,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "calmar": self.calmar,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "n_periods": self.n_periods,
            "final_equity": self.final_equity,
            "initial_equity": self.initial_equity,
        }
        d.update(self.extra)
        return d


def compute_metrics(
    equity: list[float],
    risk_free_annual: float = 0.0,
    periods_per_year: int = 252,
    trade_returns: list[float] | None = None,
) -> PerformanceMetrics:
    """Compute the full metric suite from an equity curve.

    ``trade_returns`` (per-trade P&L) is optional; when provided it adds
    win_rate and profit_factor under ``extra``.
    """
    if not equity:
        return PerformanceMetrics(
            total_return=0.0, annualized_return=0.0, annualized_volatility=0.0,
            sharpe=0.0, sortino=0.0, calmar=0.0, max_drawdown=0.0,
            var_95=0.0, cvar_95=0.0, n_periods=0,
            final_equity=0.0, initial_equity=0.0,
        )

    rets = returns_from_equity(equity)
    initial = equity[0]
    final = equity[-1]
    total_ret = (final / initial - 1.0) if initial > 0 else 0.0
    mdd, _ = max_drawdown(equity)
    n = len(rets)

    extra: dict[str, float] = {}
    if trade_returns is not None:
        extra["win_rate"] = win_rate(trade_returns)
        extra["profit_factor"] = profit_factor(trade_returns)
        extra["n_trades"] = float(len(trade_returns))

    return PerformanceMetrics(
        total_return=total_ret,
        annualized_return=annualized_return(total_ret, n, periods_per_year),
        annualized_volatility=annualized_volatility(rets, periods_per_year),
        sharpe=sharpe_ratio(rets, risk_free_annual, periods_per_year),
        sortino=sortino_ratio(rets, risk_free_annual, periods_per_year),
        calmar=calmar_ratio(total_ret, n, mdd, periods_per_year),
        max_drawdown=mdd,
        var_95=value_at_risk(rets),
        cvar_95=conditional_var(rets),
        n_periods=n,
        final_equity=final,
        initial_equity=initial,
        extra=extra,
    )


__all__ = [
    "PerformanceMetrics",
    "annualized_return",
    "annualized_volatility",
    "calmar_ratio",
    "compute_metrics",
    "conditional_var",
    "downside_deviation",
    "max_drawdown",
    "profit_factor",
    "returns_from_equity",
    "sharpe_ratio",
    "sortino_ratio",
    "value_at_risk",
    "win_rate",
]
