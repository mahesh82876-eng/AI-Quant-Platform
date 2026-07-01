"""Validation + normalization: provider rows → internal Bar model.

validate_bar: rejects NaN, non-positive prices, OHLCV invariant violations.
normalize_bars: maps arbitrary provider dicts → quant.types.Bar (UTC).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from quant.types import Bar


class DataValidationError(ValueError):
    pass


def _is_nan(x: float) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def validate_bar(open_: float, high: float, low: float, close: float, volume: float) -> None:
    for name, v in [("open", open_), ("high", high), ("low", low), ("close", close)]:
        if _is_nan(v) or v <= 0:
            raise DataValidationError(f"{name} must be positive, got {v}")
    if _is_nan(volume) or volume < 0:
        raise DataValidationError(f"volume must be >= 0, got {volume}")
    if high < max(open_, close) or low > min(open_, close) or high < low:
        raise DataValidationError(f"OHLCV invariant violated: o={open_} h={high} l={low} c={close}")


def _to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def normalize_bars(symbol: str, rows: list[dict[str, Any]]) -> list[Bar]:
    """rows: list of dicts with keys: timestamp, open, high, low, close, volume."""
    out: list[Bar] = []
    for r in rows:
        o, h, l, c, v = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])
        validate_bar(o, h, l, c, v)
        out.append(
            Bar(
                timestamp=_to_utc(r["timestamp"]),
                symbol=symbol.upper(),
                open=o, high=h, low=l, close=c, volume=v,
            )
        )
    # ensure strictly ascending
    for i in range(1, len(out)):
        if out[i].timestamp <= out[i - 1].timestamp:
            raise DataValidationError(f"bars not ascending at index {i}")
    return out
