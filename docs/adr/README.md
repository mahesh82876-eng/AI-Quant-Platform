# Architecture Decision Records (ADR)

An ADR captures *one* significant architectural decision: its context, the
options considered, the decision, and its consequences. ADRs are immutable
history — we supersede them with new ADRs, we don't edit them.

## When to write an ADR

Write one whenever a decision is:
- Hard or costly to reverse (database choice, broker abstraction).
- Affects multiple modules or future phases.
- A trade-off between reasonable alternatives.
- Mandated by an invariant (universe storage, risk enforcement, realism).

## Format

```
# ADR-NNNN: Title

- Status: proposed | accepted | superseded by ADR-XXXX | deprecated
- Date: YYYY-MM-DD
- Deciders: <roles>
- Related: ADR-XXXX

## Context
Why must we decide now? What forces are at play?

## Options considered
A, B, C — with honest trade-offs.

## Decision
What we chose, in one sentence.

## Consequences
Positive / negative / neutral. What becomes easier or harder?
```

## Numbering

- Zero-padded, monotonically increasing (`ADR-0001`).
- New ADRs are appended; never renumber.
- Superseding: set old status to "superseded by ADR-NNNN" and create a new one.

## Index

- [ADR-0001: Hexagonal architecture for the quant core](./ADR-0001-hexagonal-core.md)
- [ADR-0002: PostgreSQL + TimescaleDB as the primary store](./ADR-0002-postgres-timescale.md)
- [ADR-0003: Celery + Redis for async work](./ADR-0003-celery-redis.md)
- [ADR-0004: Data-driven trading & analysis universes](./ADR-0004-data-driven-universe.md)
- [ADR-0005: Broker abstraction (BrokerPort) — Alpaca first, IBKR later](./ADR-0005-broker-abstraction.md)
- [ADR-0006: Risk Engine as non-bypassable enforcement point](./ADR-0006-risk-enforcement.md)
- [ADR-0007: Strategy/execution symmetry (backtest = live)](./ADR-0007-strategy-execution-symmetry.md)
- [ADR-0008: Structured logging with correlation IDs](./ADR-0008-structured-logging.md)
- [ADR-0009: Typed configuration via Pydantic Settings](./ADR-0009-typed-configuration.md)
- [ADR-0010: Cloud-portable core (no AWS SDK in domain)](./ADR-0010-cloud-portability.md)
- [ADR-0011: Realistic backtests (commission + slippage + latency)](ADR-0011-realistic-backtests.md)
- [ADR-0012: One schema per bounded context](./ADR-0012-schema-per-context.md)
