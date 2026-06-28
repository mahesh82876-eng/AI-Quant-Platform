"""Pytest configuration shared by all tests.

Marks: ``unit`` (no infra) and ``integration`` (Docker services). The
``env`` fixture resets the settings cache so tests can override env vars.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Default the app into a deterministic test environment unless a test overrides.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_LOG_JSON", "false")


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Ensure ``get_settings`` re-reads env between tests that change it."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
