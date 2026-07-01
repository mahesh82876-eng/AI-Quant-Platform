"""Data layer: provider-agnostic market data ingestion.

Architecture (ADR-0001 hexagonal):
- MarketDataProvider: the port every vendor adapter implements.
- ProviderRegistry: registers providers by name; selected at runtime by config.
- Normalization: every provider response → internal Bar model (quant.types).
- Validation: rejects malformed bars before they enter the system.
- Caching: optional Redis-backed cache behind a port.

Adding a provider = implement MarketDataProvider + register it. No existing
code changes.
"""

from app.data.provider import MarketDataProvider, ProviderRegistry, get_provider
from app.data.models import BarsRequest, BarsResponse

__all__ = [
    "BarsRequest",
    "BarsResponse",
    "MarketDataProvider",
    "ProviderRegistry",
    "get_provider",
]
