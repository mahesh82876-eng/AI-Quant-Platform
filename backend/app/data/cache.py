"""Cache port + Redis + in-memory implementations (ADR-0010 cloud-portable)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class CachePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None: ...
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 300) -> None: ...


class InMemoryCache(CachePort):
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._store[key] = value


class RedisCache(CachePort):
    def __init__(self, url: str) -> None:
        self._url = url
        self._redis: Any = None

    async def _client(self) -> Any:
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._url)
        return self._redis

    async def get(self, key: str) -> Any | None:
        r = await self._client()
        raw = await r.get(key)
        return json.loads(raw) if raw else None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        r = await self._client()
        await r.set(key, json.dumps(value), ex=ttl)


def make_cache(url: str | None = None) -> CachePort:
    return RedisCache(url) if url else InMemoryCache()
