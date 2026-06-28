# ADR-0009: Typed configuration via Pydantic Settings

- Status: accepted
- Date: 2026-06-28
- Deciders: CTO, Senior Backend Engineer, Security Engineer
- Related: ADR-0008

## Context

The platform has many configuration inputs: DB/Redis URLs, broker keys, JWT
secrets, ingestion schedules, risk limits, feature toggles. Untyped config
(stringly-typed env vars read ad hoc) causes runtime failures, hidden
defaults, and secret leakage. We need fail-fast validation at startup.

## Options considered

**A. `os.environ.get(...)` scattered through the code.** No validation, no
defaults documentation, easy to misspell keys. Rejected.

**B. Dynaconf / python-dotenv alone.** Better than raw env, but loosely typed.

**C. Pydantic Settings (v2) — typed, validated, with `.env` support (chosen).**
Compile-time-ish guarantees (mypy sees the types), startup validation, nested
settings groups, and secret files support. Already aligned with FastAPI.

## Decision

Centralize all configuration in typed `BaseSettings` subclasses grouped by
concern (`DatabaseSettings`, `RedisSettings`, `BrokerSettings`, `JwtSettings`,
`RiskSettings`, …), composed into a top-level `Settings`. Loaded once at
startup from `.env` and real environment variables. Invalid config fails fast.

## Consequences

**Positive**
- Missing/malformed config is caught at boot, not at 2am during a trade.
- Types flow through the code; mypy catches misuse.
- Defaults are explicit and documented in one place.

**Negative**
- Adding a setting means editing the settings class — intended friction.

**Neutral**
- `.env.example` documents every key; `.env` is git-ignored and never logged.
- Secrets never have defaults; they must be supplied by the environment.
