# ADR-0008: Structured logging with correlation IDs

- Status: accepted
- Date: 2026-06-28
- Deciders: Senior Backend Engineer, DevOps Engineer, CTO
- Related: ADR-0009

## Context

A multi-service platform (API + workers + beat) produces logs that must be
correlatable across process boundaries: a single user request may fan out to
a worker, which reads from the DB and calls a broker. Plain text logs make
"what happened for this request/trade" nearly impossible to reconstruct. We
also must never log secrets (broker keys, JWTs, passwords).

## Options considered

**A. stdlib `logging` with a line formatter.** Simple, but unstructured and
hard to query at scale.

**B. structlog emitting JSON.** Structured, cheap, easy to ship to CloudWatch
or any log aggregator, and supports redaction filters. Chosen.

**C. loguru.** Ergonomic, but adds a dependency and diverges from stdlib
patterns that integrate cleanly with FastAPI/Celery.

**D. OpenTelemetry logs.** The future, but the logs signal is still maturing;
we adopt OTel *traces* now and can bridge structlog → OTel logs later.

## Decision

Use **structlog** with a JSON renderer in production and a pretty console
renderer in development. Every log event carries a `correlation_id` (per
request/task) propagated through context vars. A redaction processor drops
known secret keys.

## Consequences

**Positive**
- Logs are queryable by `correlation_id`, `user_id`, `strategy_id`, `order_id`.
- Secrets are filtered before emission.
- Same logger in API and workers → consistent observability.

**Negative**
- Engineers must use the structured logger, not `print` or bare `logging`.

**Neutral**
- Correlation IDs are injected by middleware (API) and task base class (Celery).
