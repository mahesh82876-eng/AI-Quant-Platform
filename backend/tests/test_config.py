"""Test that the configuration layer validates inputs and never defaults secrets.

These are pure unit tests — no Docker, no network. They guard the invariant
that misconfiguration fails fast (ADR-0009) and that secrets have no defaults.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.unit


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DB_HOST", "db.internal")
    monkeypatch.setenv("DB_PORT", "6543")
    from app.config import get_settings

    settings = get_settings()
    assert settings.env == "local"
    assert settings.db.host == "db.internal"
    assert settings.db.port == 6543


def test_dsn_is_built_from_components(monkeypatch):
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_HOST", "h")
    monkeypatch.setenv("DB_PORT", "1111")
    monkeypatch.setenv("DB_NAME", "n")
    from app.config import get_settings

    assert get_settings().db.dsn == "postgresql+psycopg://u:p@h:1111/n"


def test_redis_url_with_password(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "r")
    monkeypatch.setenv("REDIS_PORT", "6390")
    monkeypatch.setenv("REDIS_PASSWORD", "secret")
    from app.config import get_settings

    assert get_settings().redis.url == "redis://:secret@r:6390/0"


def test_broker_defaults_to_fake_and_paper(monkeypatch):
    # No BROKER_* vars set → safe Phase 1 defaults.
    for k in list(os.environ):
        if k.startswith("BROKER_"):
            monkeypatch.delenv(k, raising=False)
    from app.config import get_settings

    b = get_settings().broker
    assert b.provider == "fake"
    assert b.paper is True
    assert b.api_key is None  # no default secret
    assert b.api_secret is None


def test_log_json_forced_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_LOG_JSON", "false")  # even if someone tries to disable
    from app.config import get_settings

    assert get_settings().log_json is True


def test_invalid_env_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "not-a-real-env")
    from app.config import AppSettings

    with pytest.raises(Exception):
        AppSettings()
