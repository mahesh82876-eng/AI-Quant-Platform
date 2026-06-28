# ADR-0012: One schema per bounded context

- Status: accepted
- Date: 2026-06-28
- Deciders: Database Architect, CTO, Senior Backend Engineer
- Related: ADR-0001, ADR-0002, ADR-0004

## Context

If every engine writes to one giant `public` schema, context boundaries
(ADR-0001) exist only in code, not in data. Tables accrete, joins creep across
contexts, and a refactor to split contexts later becomes a data migration
nightmare. We want the database to *enforce* the same boundaries the code does.

## Options considered

**A. Single `public` schema, naming conventions only.** Easy start, no
enforcement; boundaries rot over time. Rejected.

**B. One database per context.** Strongest isolation, but distributed
transactions, cross-context reporting, and operational overhead are
disproportionate at this scale. Reconsider only if a context truly separates
into its own service.

**C. One database, one PostgreSQL schema per bounded context (chosen).**
Boundaries are visible and queryable; cross-context reads use explicitly
granted read models or views; writes stay within a context's schema. Clean
separation without distributed-transactions pain.

## Decision

Each bounded context owns a PostgreSQL schema: `market_data`, `macro`,
`news`, `feature_store`, `research`, `backtesting`, `ml`, `portfolio`,
`risk`, `trading`, `iam`, `audit`. Reference data shared across contexts
(instruments, universes) lives in a `reference` schema and is read-only to
other contexts.

## Consequences

**Positive**
- Data boundaries mirror code boundaries; accidental coupling is visible.
- Per-context migrations are scoped and reviewable.
- Future extraction of a context to its own DB/service is far easier.

**Negative**
- Cross-context reporting needs explicit read models/views, not ad hoc joins.

**Neutral**
- Alembic organizes migrations by context (versioned per schema or by topic).
