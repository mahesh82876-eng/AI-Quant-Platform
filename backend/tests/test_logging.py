"""Test structured logging building blocks: secret redaction and correlation
binding (ADR-0008).

We test the processors as pure functions rather than fighting structlog's
global configuration — faster, deterministic, and they're the actual logic
we care about.
"""

from __future__ import annotations

import pytest
import structlog

from app.logging import _redact_secrets, bind_context, clear_context, get_logger

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear():
    clear_context()
    yield
    clear_context()


# ---- Secret redaction (the security-critical piece) ----

def test_top_level_secret_redacted():
    out = _redact_secrets(None, "info", {"password": "hunter2", "ok": "v"})
    assert out["password"] == "***REDACTED***"
    assert out["ok"] == "v"


def test_nested_and_case_insensitive_redaction():
    out = _redact_secrets(
        None,
        "info",
        {"user": "u", "body": {"Api_Key": "sk", "Token": "t"}, "list": [{"secret": "x"}]},
    )
    assert out["body"]["Api_Key"] == "***REDACTED***"
    assert out["body"]["Token"] == "***REDACTED***"
    assert out["list"][0]["secret"] == "***REDACTED***"
    assert out["user"] == "u"


def test_non_secret_fields_preserved():
    out = _redact_secrets(
        None, "info", {"order_id": "o1", "qty": 100, "symbol": "AAPL"}
    )
    assert out == {"order_id": "o1", "qty": 100, "symbol": "AAPL"}


# ---- Correlation context binding ----

def test_bound_context_appears_in_merged_event():
    bind_context(correlation_id="cid-1", user_id="u1")
    merged = structlog.contextvars.merge_contextvars(None, "info", {"event": "x"})
    assert merged["correlation_id"] == "cid-1"
    assert merged["user_id"] == "u1"


def test_clear_context_removes_bindings():
    bind_context(correlation_id="cid-2")
    clear_context()
    merged = structlog.contextvars.merge_contextvars(None, "info", {"event": "x"})
    assert "correlation_id" not in merged


def test_logger_factory_returns_bound_logger():
    log = get_logger("test.name")
    # Bound loggers expose the structlog fluent API.
    assert hasattr(log, "info")
    assert hasattr(log, "bind")
