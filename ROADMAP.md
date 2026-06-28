# Roadmap

Eighteen phases, built strictly in order. Each phase has an **objective**,
**exit criteria**, and a **contract** it must not violate. No phase begins
until the previous one is approved.

The status emoji marks current state: ✅ done · 🚧 in progress · ⬜ not started.

---

## Phase 1 — System Architecture 🚧

**Objective:** Establish the authoritative system design, decision records, and
a runnable local topology skeleton before any feature code is written.

**Exit criteria:**
- [x] `ARCHITECTURE.md` defines components, boundaries, data flows, and security model.
- [x] ADRs recorded for foundational decisions (architecture style, DB, broker
      abstraction, universe storage, risk enforcement, realism).
- [x] `docker-compose.yml` brings up postgres + redis + api + worker + beat and
      `/health` responds.
- [x] Typed settings, structured logging, and a CI config stub exist.
- [x] Skeleton test passes (`make test`).

---

## Phase 2 — Repository Structure ⬜

**Objective:** Materialize the folder structure, tooling (ruff, mypy, pytest),
import linter (to enforce context boundaries), and the domain-core package.

**Exit criteria:** Package layout matches ARCHITECTURE.md; boundary linter
green; an empty-context import test asserts isolation; CI runs lint+type+test.

---

## Phase 3 — Database Design ⬜

**Objective:** Design schemas per context, reference/instrument model, the
data-driven trading & analysis universes, TimescaleDB hypertable plan, and
Alembic baseline.

**Exit criteria:** ERD per context; Alembic baseline migration creates schemas,
instruments, and universe tables; seed of the chartered trading universe.

---

## Phase 4 — Backend Foundation ⬜

**Objective:** FastAPI app shell, dependency-injection container, error
handling, logging middleware, pagination, health/readiness, config validation.

**Exit criteria:** App boots with all routers mounted; structured logs with
correlation IDs; global exception handler; OpenAPI auto-docs at `/docs`.

---

## Phase 5 — Authentication ⬜

**Objective:** JWT auth (access + rotating refresh), RBAC roles, password
hashing, audit log foundation, and guarded example endpoints.

**Exit criteria:** Login/refresh/logout/revoke; role decorator; live-trading
endpoints require explicit time-boxed grant; auth unit + integration tests.

---

## Phase 6 — Market Data Engine ⬜

**Objective:** `MarketDataPort` + adapter (e.g., Alpaca/polygon), ingestion
workers, normalization, corporate actions, historical + real-time storage.

**Exit criteria:** Ingest historical OHLCV for the chartered universe; bars
stored in hypertable; real-time fan-out via Redis pub/sub; adapter swappable.

---

## Phase 7 — Macro Engine ⬜

**Objective:** Macro indicators (CPI, GDP, rates, PMI, PPI, retail sales,
unemployment, treasury yields), economic calendar, regime detection model.

**Exit criteria:** Indicators stored; regime label (e.g., growth/inflation
quadrant) computed and queryable; indices feed regime but never trade.

---

## Phase 8 — News Engine ⬜

**Objective:** Market/company news, earnings, SEC filings ingestion, and an
AI-sentiment pipeline (model behind a port, results stored).

**Exit criteria:** News persisted with dedup; sentiment score attached;
configurable sources; sentiment model versioned in the registry.

---

## Phase 9 — Feature Store ⬜

**Objective:** Single source of truth for derived features — RSI, MACD, ATR,
ADX, Bollinger, returns, volatility, momentum, volume, market breadth.

**Exit criteria:** Feature plugins registered by config; idempotent
computation; materialized/cached for fast research; backtested equality proven.

---

## Phase 10 — Research Engine ⬜

**Objective:** Correlation, factor analysis, cointegration, PCA, feature
importance, heatmaps, regime analysis — exposed via API + dashboard-ready JSON.

**Exit criteria:** Analyses are pure functions over the Feature Store; results
cached; endpoints return chart-ready payloads.

---

## Phase 11 — Backtesting Engine ⬜

**CLR-protected:** always includes commission, slippage, latency. Supports
long, short, long/short, market-neutral. Walk-forward testing. Full metrics.

**Exit criteria:** Cost-aware fill model; event loop shared shape with live
runtime; walk-forward harness; metrics suite (Sharpe, Sortino, drawdown, etc.);
property tests on the fill model.

---

## Phase 12 — Machine Learning Platform ⬜

**Objective:** Train/eval pipeline for regression, classification, time-series
forecasting (RF, XGBoost, LightGBM, LSTM, Transformer). Every model saved +
versioned.

**Exit criteria:** Model registry (metadata + artifact URI); reproducible
training runs (pinned data snapshot + params); promotion path to inference.

---

## Phase 13 — Portfolio Engine ⬜

**Objective:** Track portfolio value, sector allocation, exposure,
performance; position-sizing utilities.

**Exit criteria:** Real-time portfolio state from fills; exposure by
sector/factor; performance attribution hooks; snapshot hypertable.

---

## Phase 14 — Risk Engine ⬜

**Objective:** VaR, CVaR, beta, volatility, drawdown, risk limits, and the
non-bypassable pre-trade check.

**Exit criteria:** `pre_trade_check` is the only path to the broker (test
proves it); limits configurable; post-trade risk worker runs continuously.

---

## Phase 15 — Paper Trading ⬜

**Objective:** Alpaca paper trading only. Account, buying power, positions,
orders (market/limit/stop/stop-limit/bracket), portfolio & trade history,
order status.

**Exit criteria:** `BrokerPort` Alpaca adapter; order state machine; identical
Risk Engine path as live; keys from env only; IBKR addition requires no core
change (validated by interface test).

---

## Phase 16 — Live Trading ⬜

**Objective:** Enable live trading **only after** paper validation. Reuse
paper architecture; add kill-switch, confirmation gates, and stricter limits.

**Exit criteria:** Feature-flagged; requires elevated role + explicit grant;
kill-switch stops all new orders; full audit trail.

---

## Phase 17 — Dashboard ⬜

**Objective:** Professional pages — Dashboard, Market, Stocks, Indices, Macro,
News, Research, Feature Store, Backtesting, ML, Portfolio, Risk, Paper
Trading, Settings.

**Exit criteria:** Next.js app talks only to the backend API; AG Grid + Recharts
for tables/charts; auth-gated; responsive; no business logic in the frontend.

---

## Phase 18 — Deployment ⬜

**Objective:** Productionize — CI/CD, IaC (Terraform), container images,
secrets management, observability, backups, runbooks.

**Exit criteria:** One-command deploy via pipeline; blue/green or rolling;
automated DB backups; dashboards + alerts; documented runbooks.

---

## Cross-phase invariants (must always hold)

1. **Universe is data-driven** — no hard-coded symbols in any module.
2. **Risk is enforced** — no order reaches a broker without `pre_trade_check`.
3. **Backtests are realistic** — commission + slippage + latency always on.
4. **Core is pure** — no broker/DB/framework imports in the quant domain.
5. **Secrets out of source** — `.env`/Secrets Manager only.
6. **Indices don't trade** — analysis universe never emits tradeable signals.
7. **Models are saved** — every trained model is versioned and retrievable.
