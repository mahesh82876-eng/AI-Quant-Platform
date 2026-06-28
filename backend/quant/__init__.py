"""Pure quant domain core.

This package contains the framework-independent quant domain: value objects,
market data, signals, orders, positions, strategies, and the engines
(backtesting, portfolio, risk, execution). It imports **no** infrastructure —
no FastAPI, Celery, SQLAlchemy, or broker SDKs. Everything here is unit-
testable with zero dependencies beyond NumPy/SciPy.

Boundary rule (ADR-0001): the ``app`` layer orchestrates; the ``quant`` layer
thinks. A module in ``app`` may import from ``quant``; ``quant`` may never
import from ``app``.
"""

from quant.types import (
    AssetClass,
    Bar,
    BarSeries,
    Instrument,
    MarketData,
    OrderSide,
    OrderType,
    Side,
)

__all__ = [
    "AssetClass",
    "Bar",
    "BarSeries",
    "Instrument",
    "MarketData",
    "OrderSide",
    "OrderType",
    "Side",
]
