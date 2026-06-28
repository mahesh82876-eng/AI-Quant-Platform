# ADR-0003: Celery + Redis for async work

- Status: accepted
- Date: 2026-06-28
- Deciders: CTO, Senior Backend Engineer, DevOps Engineer
- Related: ADR-0002

## Context

The platform has substantial async workloads: scheduled data ingestion
( market/macro/news), long-running backtests, model training, continuous
post-trade risk, and report generation. These must run outside the
request/response cycle, be retriable, observable, and schedulable.

## Options considered

**A. Celery + Redis (broker + result backend) + Celery beat for scheduling.**
Mature, widely understood, good Python/FastAPI ergonomics, retry and
scheduling built in. Chosen.

**B. RQ (Redis Queue).** Simpler than Celery, but weaker scheduling and
less expressive task pipelines; would need augmentation as we grow.

**C. Dramatiq.** Cleaner API than Celery, but smaller ecosystem and less
familiarity across teams.

**D. A full event-streaming platform (Kafka).** Excellent for high-throughput
event pipelines, but heavy operational complexity before we need it. Redis
Streams remains an option inside Redis if pub/sub is insufficient.

**E. APScheduler in-process.** Fine for tiny jobs, but doesn't survive process
restarts or scale horizontally; not suitable for backtests/training.

## Decision

Use **Celery with Redis as broker and result backend**, plus **Celery beat**
for cron-style scheduling. Tasks are thin orchestrators — they call into the
domain; they contain no business logic.

## Consequences

**Positive**
- Horizontal scaling of workers; separate queues per workload class
  (`ingest`, `compute`, `backtest`, `ml`, `default`).
- Built-in retry, exponential backoff, and task-level observability.
- Familiar to most backend engineers.

**Negative**
- Celery's API surface and configuration have rough edges; we hide these
  behind a thin `tasks/` facade with typed wrappers.
- A broker is now required infrastructure (acceptable; we already run Redis).

**Neutral**
- Task idempotency must be designed in (e.g., ingestion keyed by
  symbol+timestamp) so retries are safe.
