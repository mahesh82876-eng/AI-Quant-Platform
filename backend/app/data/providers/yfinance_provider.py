"""yfinance provider — for local development only (ADR-0010: no hard vendor lock).

Adds yfinance as an optional dep. Falls back gracefully if not installed.
Production swaps in Polygon/Alpaca/Databento/Alpha Vantage by registering a
new MarketDataProvider subclass — no existing code changes.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

from app.data.models import BarsRequest, BarsResponse
from app.data.normalize import normalize_bars
from app.data.provider import MarketDataProvider, get_registry


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    def __init__(self) -> None:
        self._installed = self._check_installed()

    @staticmethod
    def _check_installed() -> bool:
        try:
            import yfinance  # noqa: F401
            return True
        except ImportError:
            return False

    async def get_bars(self, request: BarsRequest) -> BarsResponse:
        if not self._installed:
            raise RuntimeError("yfinance not installed; pip install yfinance")
        import yfinance as yf

        period_map = {"1Day": "1d", "1Hour": "1h", "1Min": "1m"}
        interval = period_map.get(request.timeframe, "1d")
        df = await asyncio.to_thread(
            yf.download,
            request.symbol,
            start=request.start.date().isoformat(),
            end=request.end.date().isoformat(),
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        rows = []
        for ts, row in df.iterrows():
            rows.append({
                "timestamp": ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                "open": row["Open"], "high": row["High"], "low": row["Low"],
                "close": row["Close"], "volume": row["Volume"],
            })
        bars = normalize_bars(request.symbol, rows)
        return BarsResponse(symbol=request.symbol, bars=bars, provider=self.name)


def register_default() -> None:
    """Register the dev provider. Call once at app startup."""
    reg = get_registry()
    if "yfinance" not in reg.names:
        reg.register(YFinanceProvider())
