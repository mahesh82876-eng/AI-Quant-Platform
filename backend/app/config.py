"""Typed application configuration (ADR-0009).

All runtime configuration is centralized here as typed Pydantic Settings,
loaded from environment variables and a local ``.env`` file. Invalid or
missing required configuration fails fast at startup — never at 2 AM during
a trade.

Secrets (broker keys, JWT signing keys) have **no defaults** and must be
supplied by the environment. They are never logged (see ``logging.py``).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL + TimescaleDB connection (ADR-0002)."""

    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str = "quant"
    password: SecretStr = Field(default=SecretStr("quant"))
    name: str = "quant_platform"
    pool_size: int = 10
    pool_max_overflow: int = 20

    @property
    def dsn(self) -> str:
        """Asynchronous-style SQLAlchemy DSN."""
        pw = self.password.get_secret_value()
        return f"postgresql+psycopg://{self.user}:{pw}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis: Celery broker + result backend + cache (ADR-0003)."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None

    @property
    def url(self) -> str:
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class BrokerSettings(BaseSettings):
    """Broker adapter selection (ADR-0005).

    Phase 1 only stores the shape; the Alpaca adapter is implemented in
    Phase 15. Keys have no defaults and must come from the environment.
    """

    model_config = SettingsConfigDict(env_prefix="BROKER_", env_file=".env", extra="ignore")

    provider: Literal["alpaca", "ibkr", "fake"] = "fake"
    paper: bool = True  # paper trading only until Phase 16
    api_key: SecretStr | None = None
    api_secret: SecretStr | None = None
    base_url: str | None = None


class JwtSettings(BaseSettings):
    """JWT authentication (Phase 5)."""

    model_config = SettingsConfigDict(env_prefix="JWT_", env_file=".env", extra="ignore")

    algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    signing_key: SecretStr | None = None  # no default; must be supplied
    issuer: str = "quant-platform"


class RiskSettings(BaseSettings):
    """Top-level risk toggles. Detailed limits are Phase 14."""

    model_config = SettingsConfigDict(env_prefix="RISK_", env_file=".env", extra="ignore")

    enforce_pre_trade: bool = True  # ADR-0006: the kill-switch default
    max_gross_exposure_pct: float = 100.0
    max_single_position_pct: float = 10.0


class AppSettings(BaseSettings):
    """Top-level settings composed of all subsystem settings."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    name: str = "quant-platform"
    env: Literal["local", "test", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = False  # pretty console locally, JSON in production

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)

    @field_validator("log_json")
    @classmethod
    def _json_in_prod(cls, v: bool, info) -> bool:  # type: ignore[no-untyped-def]
        # Force structured JSON logs in non-local environments (ADR-0008).
        env = info.data.get("env", "local")
        return True if env in {"staging", "production"} else v


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return the cached, validated application settings.

    Cached for the lifetime of the process. Tests call ``get_settings.cache_clear()``
    to reset between parameterized runs.
    """
    return AppSettings()
