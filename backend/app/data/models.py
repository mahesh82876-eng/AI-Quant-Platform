"""Request/response contracts for the data layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class BarsRequest:
    symbol: str
    start: datetime
    end: datetime
    timeframe: str = "1Day"  # 1Day | 1Hour | 1Min (provider-normalized)


@dataclass(frozen=True)
class BarsResponse:
    symbol: str
    bars: list[Any]  # list[quant.types.Bar]
    provider: str
    cached: bool = False
    warnings: list[str] = field(default_factory=list)
