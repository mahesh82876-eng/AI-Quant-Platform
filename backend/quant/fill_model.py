"""Cost and fill models for realistic backtesting (ADR-0011).

Realism is mandatory, not optional: every fill carries commission + slippage,
and every order is subject to a latency assumption. A backtest with zero costs
must be an explicit, logged, *idealized* configuration — never the silent
default.

The fill model is also the simulator the execution layer uses for paper
trading's internal "what-if" path; the only difference in paper/live is that
real broker fills replace the simulated ones.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from quant.orders import Fill, Order, OrderSide, OrderType
from quant.types import Bar


# ──────────────────────────────── Cost model ────────────────────────────────


@dataclass(frozen=True)
class CostModel:
    """How much a trade costs the book.

    Commission: ``per_share`` *and/or* ``percent_notional`` (whichever is
    configured; both apply additively). Slippage is in basis points relative
    to the fill price. Defaults reflect a realistic retail/paper baseline;
    real deployment calibrates these to actual broker fills.
    """

    commission_per_share: float = 0.005  # $0.005/share (e.g., Alpaca-ish)
    commission_percent: float = 0.0  # fraction of notional (e.g., 0.0005 = 5bps)
    commission_min: float = 1.0  # minimum ticket charge
    slippage_bps: float = 5.0  # 5 bps of price paid/received
    idealized: bool = False  # if True, zero everything (must be explicit)

    def commission(self, quantity: float, price: float) -> float:
        if self.idealized:
            return 0.0
        per_share = self.commission_per_share * abs(quantity)
        pct = self.commission_percent * abs(quantity) * price
        return max(self.commission_min, per_share + pct)

    def slippage(self, price: float) -> float:
        """Absolute price impact (always adverse to the trader)."""
        if self.idealized:
            return 0.0
        return price * (self.slippage_bps / 10_000.0)


IDEALIZED_COSTS = CostModel(idealized=True)
DEFAULT_COSTS = CostModel()


# ──────────────────────────────── Fill model ────────────────────────────────


class FillModel(ABC):
    """Translate an :class:`Order` + the bar it executes against into a Fill.

    Subclasses decide fill price, fill quantity (partial fills allowed), and
    attach the cost model's commission. Rejections (e.g., stop not triggered)
    return an empty list.
    """

    @abstractmethod
    def fill(self, order: Order, bar: Bar, cost: CostModel) -> list[Fill]:
        """Return fills (possibly empty / possibly multiple for partials)."""
        raise NotImplementedError


@dataclass
class SimpleFillModel(FillModel):
    """A transparent, conservative fill model suitable for daily-bar backtests.

    Rules:
    - MARKET: fill at bar close +/- slippage. Full quantity.
    - LIMIT: fill at ``limit_price`` only if the bar traded through it
      (low ≤ limit ≤ high for buys; vice versa for sells). No partials.
    - STOP: triggers when the bar's low/high crosses ``stop_price``; then
      fills at the stop (slippage applied) — modeling a stop becoming a market.
    - STOP_LIMIT: stop triggers as above, then fills at the limit only if the
      bar also reaches the limit after the stop.

    All fills apply :class:`CostModel` commission and slippage. This is the
    conservative default; a more sophisticated model (e.g., VWAP, order-book)
    can subclass :class:`FillModel` without touching the engines.
    """

    def fill(self, order: Order, bar: Bar, cost: CostModel) -> list[Fill]:
        fill_price = self._resolve_price(order, bar)
        if fill_price is None:
            return []  # order not fillable this bar

        # Slippage always moves price against the trader.
        slip = cost.slippage(fill_price)
        if order.side == OrderSide.BUY:
            fill_price += slip
        else:
            fill_price -= slip

        commission = cost.commission(order.quantity, fill_price)
        return [
            Fill(
                timestamp=bar.timestamp,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=commission,
                order_type=order.order_type,
            )
        ]

    def _resolve_price(self, order: Order, bar: Bar) -> float | None:
        t = order.order_type
        if t == OrderType.MARKET:
            return bar.close
        if t == OrderType.LIMIT:
            return self._limit_fill_price(order, bar)
        if t == OrderType.STOP:
            return self._stop_fill_price(order, bar)
        if t == OrderType.STOP_LIMIT:
            return self._stop_limit_fill_price(order, bar)
        # BRACKET is decomposed into legs by the execution layer before fill.
        raise NotImplementedError(f"Fill for {t} must be decomposed into legs")


    def _limit_fill_price(self, order: Order, bar: Bar) -> float | None:
        lp = order.limit_price
        assert lp is not None
        if order.side == OrderSide.BUY and bar.low <= lp <= bar.high:
            return lp
        if order.side == OrderSide.SELL and bar.low <= lp <= bar.high:
            return lp
        return None

    def _stop_fill_price(self, order: Order, bar: Bar) -> float | None:
        sp = order.stop_price
        assert sp is not None
        if order.side == OrderSide.BUY and bar.high >= sp:
            return sp  # triggered; fill at stop (conservative)
        if order.side == OrderSide.SELL and bar.low <= sp:
            return sp
        return None

    def _stop_limit_fill_price(self, order: Order, bar: Bar) -> float | None:
        # Stop must trigger, then the limit must be reachable in the same bar.
        if self._stop_fill_price(order, bar) is None:
            return None
        return self._limit_fill_price(order, bar)


__all__ = [
    "CostModel",
    "DEFAULT_COSTS",
    "FillModel",
    "IDEALIZED_COSTS",
    "SimpleFillModel",
]
