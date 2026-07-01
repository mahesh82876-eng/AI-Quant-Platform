"""Data layer tests — validation, normalization, cache, registry, ingestion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.data.cache import InMemoryCache
from app.data.models import BarsRequest, BarsResponse
from app.data.normalize import DataValidationError, normalize_bars, validate_bar
from app.data.provider import MarketDataProvider, ProviderRegistry

pytestmark = pytest.mark.unit


# ---- validation / normalization ----

def test_validate_bar_accepts_valid():
    validate_bar(100, 102, 99, 101, 1000)  # no raise


def test_validate_bar_rejects_negative_price():
    with pytest.raises(DataValidationError):
        validate_bar(-1, 102, 99, 101, 1000)


def test_validate_bar_rejects_ohlcv_invariant():
    with pytest.raises(DataValidationError):
        validate_bar(100, 99, 101, 100, 1000)  # high < open


def test_normalize_bars_roundtrip():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"timestamp": t0, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"timestamp": t0 + timedelta(days=1), "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1100},
    ]
    bars = normalize_bars("aapl", rows)
    assert len(bars) == 2
    assert bars[0].symbol == "AAPL"
    assert bars[1].close == 102


def test_normalize_bars_rejects_descending():
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {"timestamp": t0 + timedelta(days=1), "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000},
        {"timestamp": t0, "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1100},
    ]
    with pytest.raises(DataValidationError):
        normalize_bars("AAPL", rows)


def test_normalize_bars_naive_datetime_becomes_utc():
    t0 = datetime(2026, 1, 1)  # naive
    rows = [{"timestamp": t0, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000}]
    bars = normalize_bars("AAPL", rows)
    assert bars[0].timestamp.tzinfo is not None


# ---- cache ----

async def test_inmemory_cache_set_get():
    c = InMemoryCache()
    await c.set("k", {"v": 1})
    assert await c.get("k") == {"v": 1}
    assert await c.get("missing") is None


# ---- registry ----

class _FakeProvider(MarketDataProvider):
    name = "fake"

    async def get_bars(self, request: BarsRequest) -> BarsResponse:
        return BarsResponse(symbol=request.symbol, bars=[], provider=self.name)


def test_registry_register_get():
    r = ProviderRegistry()
    p = _FakeProvider()
    r.register(p)
    assert r.get("fake") is p
    assert "fake" in r.names


def test_registry_unknown_raises():
    r = ProviderRegistry()
    with pytest.raises(KeyError):
        r.get("nope")


# ---- ingestion service ----

class _CountingProvider(MarketDataProvider):
    name = "counting"
    def __init__(self): self.calls = 0
    async def get_bars(self, request: BarsRequest) -> BarsResponse:
        self.calls += 1
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        from quant.types import Bar
        bars = [Bar(timestamp=t0, symbol="AAPL", open=100, high=101, low=99, close=100, volume=1000)]
        return BarsResponse(symbol=request.symbol, bars=bars, provider=self.name)


async def test_ingestion_caches_second_call():
    from app.data.ingestion import IngestionService
    p = _CountingProvider()
    svc = IngestionService(provider=p, cache=InMemoryCache())
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    req = BarsRequest(symbol="AAPL", start=t0, end=t0 + timedelta(days=5))
    r1 = await svc.fetch(req)
    r2 = await svc.fetch(req)
    assert p.calls == 1  # only fetched once
    assert r1.cached is False
    assert r2.cached is True
    assert len(r2.bars) == 1
