# Architecture

This document defines the system design for the Institutional AI Quant
Research & Trading Platform. It is the authoritative source for component
boundaries, data flows, and cross-cutting concerns. Every later phase must be
consistent with this document or update it via an ADR.

> Read [`ROADMAP.md`](./ROADMAP.md) first for the phase-by-phase build order.

---

## 1. Design philosophy

### 1.1 Hexagonal (Ports & Adapters) core

The quant domain — strategies, risk, portfolio, signals, backtests — is **pure
Python**. It depends on abstractions (ports), never on concrete infrastructure.
Brokers, data vendors, databases, and message queues are **adapters** that plug
into those ports.

Consequences:
- The **Risk Engine** can be unit-tested with zero infrastructure by supplying
  a fake broker and in-memory positions.
- A new broker (e.g., Interactive Brokers after Alpaca) is a new adapter behind
  the same `BrokerPort` — the core never changes. (ADR-0005)
- Backtests and live trading share the same strategy interface, so a strategy
  validated in backtest runs unmodified in paper/live. (ADR-0007)

### 1.2 Bounded contexts

Each engine is a bounded context with one responsibility, a public
interface (service/facade), and private internals. Contexts communicate
through well-defined contracts, never by reaching into each other's internals.

```
market_data  macro        news         feature_store
research      backtesting  ml_platform  portfolio
risk          trading      (paper/live) surveillance (later)
```

### 1.3 Realism by default

Backtests always include commission, slippage, and latency assumptions
(ADR-0011). The universe is data-driven and stored in the database (ADR-0004).
The Risk Engine is a non-bypassable enforcement point (ADR-0006).

---

## 2. Logical architecture

```
                 ┌──────────────────────────────────────────────┐
                 │              Frontend (Next.js)              │
                 │  Dashboard · Research · Risk · Trading · ...  │
                 └───────────────┬──────────────────────────────┘
                                 │ HTTPS / REST + WebSocket
                 ┌───────────────▼──────────────────────────────┐
                 │            Backend (FastAPI)                 │
                 │   API layer · Auth · WebSocket gateway         │
                 └───┬───────────┬───────────┬───────────┬──────┘
                     │           │           │           │
        ┌────────────▼──┐ ┌──────▼─────┐ ┌───▼────────┐ ┌▼─────────────┐
        │  Async workers│ │ Postgres   │ │   Redis    │ │ Object store │
        │  (Celery)     │ │ +Timescale │ │ cache/queue│ │ (S3/minio)*  │
        └───────────────┘ └────────────┘ └────────────┘ └──────────────┘
                │
   ┌────────────┴───────────────────────────────────────────────┐
   │                 External adapters (ports)                    │
   │  market data vendors · macro feeds · news · broker (Alpaca) │
   └────────────────────────────────────────────────────────────┘

   * object store introduced in the phase that needs it (ML artifacts)
```

### 2.1 Component responsibilities

| Context          | Owns                                             | Does NOT do                                  |
| ---------------- | ------------------------------------------------ | -------------------------------------------- |
| market_data      | Ingesting, normalizing, storing OHLCV & corp. actions | Strategy logic, trading decisions            |
| macro            | Economic indicators, regime detection            | Direct trading signals                       |
| news             | News/filings ingestion, sentiment scoring        | Signal generation from indices               |
| feature_store    | Technical indicators & derived features          | Raw data storage                             |
| research         | Statistical analysis (corr, cointegration, PCA)  | Order execution                              |
| backtesting      | Replay simulation with costs                     | Live market access                           |
| ml_platform      | Training, registry, serving models               | Database access beyond its schema            |
| portfolio        | Holdings, allocation, exposure                   | Risk enforcement                             |
| risk             | Limits, VaR/CVaR, pre/post-trade checks          | Placing orders                               |
| trading          | Broker adapters, order state machine             | Deciding to trade (that's strategy)          |
| surveillance     | Audit, anomaly detection (later)                 | —                                            |

---

## 3. Process topology

### 3.1 Local development (docker-compose)

```
nginx/edge (later) ─ web (Next.js, :3000)
                  └─ api (FastAPI, :8000) ──┬── postgres (:5432)
                                            ├── redis (:6379)
                                            ├── worker (Celery)
                                            ├── beat (Celery beat)
                                            └── mailhog (later)
```

### 3.2 Production target (AWS, sketched)

```
Route 53 → CloudFront/ALB → ECS Fargate (web, api, worker, beat)
                            ├─ RDS PostgreSQL (Multi-AZ) + TimescaleDB
                            ├─ ElastiCache Redis
                            ├─ S3 (artifacts/models/exports)
                            ├─ Secrets Manager (API keys, JWT secret)
                            └─ CloudWatch + X-Ray (logs/metrics/traces)
```

**No AWS SDK is imported in the core.** Cloud concerns are isolated in
`infra/` and adapters, keeping the platform portable. (ADR-0010)

---

## 4. Data architecture

### 4.1 PostgreSQL + TimescaleDB

- **Hypertables** for time-series: OHLCV bars, macro indicators, features,
  portfolio snapshots, order events, risk metrics.
- **Relational tables** for reference data: instruments, trading universe
  membership, users, strategies, models registry.
- **One schema per context** (`market_data`, `portfolio`, `risk`, `ml`, etc.)
  to keep boundaries explicit. Cross-schema access is the exception, done
  through read models, not by joining into another context's internals.

### 4.2 Redis

- Celery broker + result backend.
- Hot read cache for feature lookups and dashboard endpoints.
- Real-time price fan-out via pub/sub → WebSocket gateway.

### 4.3 Data ownership & contracts

Data flows between contexts as typed Pydantic contracts, not raw dicts. Each
context exposes only what its public interface promises. The Feature Store is
the single source of truth for derived features; no context recomputes RSI
privately.

---

## 5. Cross-cutting concerns

| Concern        | Approach                                                                 |
| -------------- | ------------------------------------------------------------------------ |
| Configuration  | Typed settings from `.env` via Pydantic Settings; no hard-coded secrets   |
| Secrets        | `.env` locally; AWS Secrets Manager in prod (never in source/images)     |
| Logging        | Structured JSON logs (structlog), correlation IDs, request IDs           |
| Observability  | OpenTelemetry-compatible spans; metrics exported to CloudWatch (later)   |
| Error handling | Domain errors as typed exceptions; API translates to HTTP via handlers   |
| Transactions   | Unit-of-Work pattern; no business logic inside DB transactions longer than necessary |
| Migrations     | Alembic, review-required, reversible                                     |
| Testing        | Pytest; domain unit tests need no infrastructure                         |
| Security       | JWT (short access + refresh), RBAC, secrets in Secrets Manager           |
| Async          | Celery for ingestion/backtest/training; FastAPI async for I/O-bound API  |

---

## 6. Security model (preview — full design in Phase 5)

- **AuthN:** OAuth2 password flow → JWT access token (short TTL) + refresh
  token (rotating). Refresh tokens stored hashed in Redis/DB.
- **AuthZ:** RBAC with roles (`researcher`, `trader`, `risk_manager`, `admin`).
  Live-trading endpoints additionally require an explicit, time-boxed grant.
- **Secrets:** Broker API keys live only in Secrets Manager / `.env`; the app
  reads them at runtime. No key is ever logged.
- **Audit:** Every order, risk override, and config change is written to an
  append-only audit log.

---

## 7. The two universes (data-driven, never hard-coded)

> Mandated by the project charter; enforced here as a hard architectural rule.

- **Trading Universe** — tradable instruments used for signal generation,
  backtesting, and trading. Stored in `universe_membership` keyed by a named
  universe (e.g., `default`). New symbols are added by a row insert, never a
  code change. (ADR-0004)
- **Market Analysis Universe** — indices used for regime/trend/sector analysis
  **only**. Indices never generate trades directly. Enforced at the
  `SignalEmitter` boundary: signals from instruments flagged `is_index=true`
  are rejected for trading.

---

## 8. The Risk Engine as enforcement point

The Risk Engine is the single chokepoint between a strategy's intent and a
broker. The execution path is:

```
Strategy → Signal → RiskEngine.pre_trade_check(signal, portfolio, context)
                     ├── PASS  → Order → BrokerAdapter.submit()
                     └── REJECT (reason) → record + notify
```

No code path to a broker bypasses `pre_trade_check`. This is verified by a test
that asserts every order submission is preceded by a recorded risk check
(ADR-0006). Post-trade risk (VaR/CVaR/drawdown) runs continuously in a worker.

---

## 9. Strategy & execution symmetry (backtest ↔ live)

A strategy is a pure function `(bars, features, context) -> Optional[Signal]`.
The same strategy object runs inside the backtester's event loop and the live
trader's event loop. Differences live in the **runtime**, not the strategy:

| Aspect        | Backtest runtime       | Live runtime            |
| ------------- | ---------------------- | ----------------------- |
| Data source   | Historical replay      | Real-time broker feed   |
| Order routing | Simulated fill model   | Broker adapter          |
| Clock         | Event-driven synthetic | Wall clock              |
| Risk          | Same RiskEngine        | Same RiskEngine         |
| Costs         | Fill model (slip+comm) | Actual broker costs     |

This symmetry is what makes a validated backtest a credible precursor to live
trading (ADR-0007).

---

## 10. Extensibility points

- **New tradable asset:** insert instrument + universe row → no code change.
- **New market-data vendor:** implement `MarketDataPort`; register adapter.
- **New broker:** implement `BrokerPort`; reuse Risk Engine and strategies.
- **New feature:** add a `Feature` plugin to the Feature Store; registered by
  config, not by editing a core module.
- **New strategy:** implement `Strategy` ABC; declare universe + risk params
  via config. No engine changes required.

---

## 11. What we explicitly avoid (anti-corruption)

- No notebooks in the platform (research notebooks live outside the repo or in
  a sandbox).
- No throwaway scripts; every script becomes a tested, configured command.
- No cross-context imports of internal modules — only public interfaces.
- No raw-SQL scattered in services; persistence is adapter-isolated.
- No business logic in API handlers or Celery tasks; they orchestrate.
- No hard-coded symbols, costs, limits, or secrets anywhere.

---

## 12. Open questions (resolved by ADR or later phases)

1. **Self-hosted TimescaleDB vs managed** — defer to Phase 3 (DB Design).
2. **Model artifact store** — S3 vs DB blobs; decided in Phase 12 (ML).
3. **Streaming pipeline** — Kafka vs Redis Streams for tick data at scale;
   defer until a phase needs it.
4. **Multi-tenant vs single-org** — assumed single-org internal platform;
   revisit if requirements change.

---

## References

- [`ROADMAP.md`](./ROADMAP.md) — phase plan and exit criteria.
- [`docs/adr/`](./docs/adr/) — Architecture Decision Records.
- [`docs/adr/README.md`](./docs/adr/README.md) — how to add a new ADR.
