"""Ingestion service: orchestrates provider → validate → cache → persist.

Clean separation: provider fetches, normalize validates, cache speeds up
re-reads, and the repository persists to the Phase 3 market_data schema.
"""

from __future__ import annotations

from __future__ import annotations

from typing import Any

from app.data.cache import CachePort, make_cache
from app.data.models import BarsRequest, BarsResponse
from app.data.provider import MarketDataProvider


class BarsRepository:
    """Persists bars to market_data.ohlcv_bar (Phase 3 schema)."""

    def __init__(self, session_factory: Any = None) -> None:
        self._sf = session_factory  # async session factory; None in unit tests

    async def save(self, response: BarsResponse) -> int:
        if self._sf is None:
            return 0
        from app.models.market_data import OhlcvBar
        from quant.types import Bar
        n = 0
        async with self._sf() as session:
            for b in response.bars:
                bar: Bar = b
                session.add(OhlcvBar(
                    symbol=bar.symbol, timestamp=bar.timestamp,
                    open=bar.open, high=bar.high, low=bar.low, close=bar.close, volume=bar.volume,
                ))
                n += 1
            await session.commit()
        return n


class IngestionService:
    """Provider → cache → DB orchestration."""

    def __init__(self, provider: MarketDataProvider, cache: CachePort | None = None,
                 repository: BarsRepository | None = None) -> None:
        self._provider = provider
        self._cache = cache or make_cache()
        self._repo = repository or BarsRepository()

    def _key(self, r: BarsRequest) -> str:
        return f"bars:{r.symbol}:{r.timeframe}:{r.start.isoformat()}:{r.end.isoformat()}"

    async def fetch(self, request: BarsRequest) -> BarsResponse:
        cached = await self._cache.get(self._key(request))
        if cached:
            from quant.types import Bar
            bars: list[Bar] = [Bar(**b) for b in cached]
            return BarsResponse(symbol=request.symbol, bars=bars, provider=self._provider.name, cached=True)
        response = await self._provider.get_bars(request)
        await self._cache.set(self._key(request), [dict(b.__dict__) for b in response.bars])
        await self._repo.save(response)
        return response
