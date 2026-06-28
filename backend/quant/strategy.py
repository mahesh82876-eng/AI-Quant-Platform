"""Strategy interface and example strategies.

A :class:`Strategy` is a pure mapping from market data + portfolio state to
zero or more :class:`~quant.orders.Signal` objects. It has **no** access to
the future, the broker, or the clock — those are injected by the runtime.
This purity is what lets the same strategy object run in the backtester and
the live trader (ADR-0007).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from quant.orders import Signal
from quant.portfolio import Portfolio
from quant.types import BarSeries, MarketData


class Strategy(ABC):
    """The strategy contract.

    Subclasses implement :meth:`on_bar`. The runtime calls ``on_bar`` once per
    timestamp with the *trailing* data (no lookahead) and the current
    portfolio. Implementations must be stateless across calls *except* for
    internal state they own (e.g., a moving-average cache); they must never
    mutate the portfolio or reach into the future.
    """

    name: str = "base"

    @abstractmethod
    def on_bar(
        self,
        timestamp: datetime,
        data: MarketData,
        portfolio: Portfolio,
    ) -> list[Signal]:
        """Return signals for ``timestamp``. Empty list means hold/do nothing."""
        raise NotImplementedError

    def universe(self) -> list[str] | None:
        """Symbols this strategy trades. ``None`` = trade whatever it sees."""
        return None


# ─────────────────────────── Example strategies ───────────────────────────
# These are runnable, tested strategies — not placeholders. They demonstrate
# the contract and give the engines something concrete to exercise. A real
# platform adds strategies by subclassing ``Strategy``; no engine changes.


class BuyAndHoldStrategy(Strategy):
    """Allocate the whole book to one symbol on the first bar, then hold."""

    name = "buy_and_hold"

    def __init__(self, symbol: str, target_weight: float = 1.0) -> None:
        self.symbol = symbol.upper()
        self.target_weight = target_weight
        self._entered = False

    def on_bar(self, timestamp: datetime, data: MarketData, portfolio: Portfolio) -> list[Signal]:
        if self._entered:
            return []
        if data.get(self.symbol) is None:
            return []
        self._entered = True
        return [Signal.target_weight(self.symbol, self.target_weight, ts=timestamp, reason="initial_entry")]


class MovingAverageCrossStrategy(Strategy):
    """Long when fast SMA > slow SMA; flat otherwise. Single symbol.

    A classic, fully-specified trend-following rule. Emits a target weight of
    +1 (fully invested) on a golden cross, 0 (go to cash) on a death cross.
    """

    name = "ma_cross"

    def __init__(self, symbol: str, fast: int = 20, slow: int = 50, target_weight: float = 1.0) -> None:
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be < slow ({slow})")
        self.symbol = symbol.upper()
        self.fast = fast
        self.slow = slow
        self.target_weight = target_weight
        self._prev_state: int | None = None  # +1 long, 0 flat

    @staticmethod
    def _sma(closes: list[float], window: int) -> float | None:
        if len(closes) < window:
            return None
        return sum(closes[-window:]) / window

    def on_bar(self, timestamp: datetime, data: MarketData, portfolio: Portfolio) -> list[Signal]:
        series = data.get(self.symbol)
        if series is None or len(series) < self.slow:
            return []
        closes = series.closes
        fast_ma = self._sma(closes, self.fast)
        slow_ma = self._sma(closes, self.slow)
        if fast_ma is None or slow_ma is None:
            return []

        state = 1 if fast_ma > slow_ma else 0
        if state == self._prev_state:
            return []  # no change → no signal
        self._prev_state = state
        w = self.target_weight if state == 1 else 0.0
        return [Signal.target_weight(self.symbol, w, ts=timestamp,
                                      reason="golden_cross" if state else "death_cross")]


class RandomStrategy(Strategy):
    """Uniformly random target weight each bar — a noise baseline for testing.

    Seeded for reproducibility. Never use this for real trading; it exists so
    the engines can be exercised with a signal source that has no lookahead
    and unpredictable behavior.
    """

    name = "random"

    def __init__(self, symbols: list[str], seed: int = 0, max_weight: float = 0.1) -> None:
        import random

        self.symbols = [s.upper() for s in symbols]
        self.max_weight = max_weight
        self._rng = random.Random(seed)

    def on_bar(self, timestamp: datetime, data: MarketData, portfolio: Portfolio) -> list[Signal]:
        out: list[Signal] = []
        for s in self.symbols:
            if data.get(s) is None:
                continue
            w = self._rng.uniform(-self.max_weight, self.max_weight)
            out.append(Signal.target_weight(s, round(w, 4), ts=timestamp, reason="random"))
        return out


__all__ = [
    "BuyAndHoldStrategy",
    "MovingAverageCrossStrategy",
    "RandomStrategy",
    "Strategy",
]
