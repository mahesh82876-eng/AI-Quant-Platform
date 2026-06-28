# ADR-0002: PostgreSQL + TimescaleDB as the primary store

- Status: accepted
- Date: 2026-06-28
- Deciders: CTO, Database Architect, Senior Data Engineer
- Related: ADR-0012

## Context

The platform stores two very different shapes of data: (1) relational
reference data — instruments, universes, users, strategies, models — and
(2) massive append-mostly time-series — OHLCV bars, features, portfolio
snapshots, risk metrics, order events. We need ACID, rich indexing, and a
single operational story.

## Options considered

**A. PostgreSQL for relational + TimescaleDB extension for time-series.**
One engine, one operational model, ACID across both, mature tooling, and
Timescale's hypertables/compression/continuous aggregates handle the
time-series load. Chosen.

**B. PostgreSQL + a separate TSDB (InfluxDB / QuestDB).** Best-of-breed
time-series, but two engines, two backup stories, cross-store transactions
impossible, and more operational surface.

**C. Pure columnar (ClickHouse) for analytics + Postgres for OLTP.**
Excellent for heavy analytics, but overkill at this stage and adds a second
engine. Could be added later as a research/OLAP read-side if needed.

**D. A document store (MongoDB).** Flexible schema, but we lose strict
contracts and relational integrity for reference data. Rejected.

## Decision

Use **PostgreSQL 16 with the TimescaleDB extension** as the single primary
datastore. Time-series go into hypertables; reference data into normal
relational tables.

## Consequences

**Positive**
- One engine to operate, back up, and secure.
- ACID guarantees across reference and time-series data.
- Continuous aggregates let us precompute common analytics (e.g., weekly
  returns, rolling vol) without a second store.
- Alembic migrations work across the whole schema.

**Negative**
- At extreme tick-data volume we may eventually need a dedicated TSDB or
  columnar store; deferred until a phase proves the need (ARCHITECTURE.md §12).
- TimescaleDB must be installed in the Postgres image and on RDS (supported).

**Neutral**
- Schemas are namespaced per bounded context (ADR-0012).
