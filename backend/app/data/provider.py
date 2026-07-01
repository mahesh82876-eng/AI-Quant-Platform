"""MarketDataProvider port + registry (ADR-0001, ADR-0005-style abstraction)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.data.models import BarsRequest, BarsResponse


class MarketDataProvider(ABC):
    """Port every data vendor implements. New provider = new subclass + register."""

    name: str = "base"

    @abstractmethod
    async def get_bars(self, request: BarsRequest) -> BarsResponse:
        raise NotImplementedError

    async def health(self) -> bool:
        return True


class ProviderRegistry:
    """Name → provider map. Selected at runtime by config."""

    def __init__(self) -> None:
        self._providers: dict[str, MarketDataProvider] = {}

    def register(self, provider: MarketDataProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> MarketDataProvider:
        if name not in self._providers:
            raise KeyError(f"provider '{name}' not registered; known: {list(self._providers)}")
        return self._providers[name]

    @property
    def names(self) -> list[str]:
        return list(self._providers)


# ---- Singleton registry + DI ----
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return _registry


def get_provider(name: str | None = None) -> MarketDataProvider:
    from app.config import get_settings
    name = name or get_settings().broker.provider  # reuse provider selector
    # Fall back: data provider may differ from broker; use DATA_PROVIDER env.
    import os
    name = os.environ.get("DATA_PROVIDER", name)
    return get_registry().get(name)
