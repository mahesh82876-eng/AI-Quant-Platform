# ADR-0004: Data-driven trading & analysis universes

- Status: accepted
- Date: 2026-06-28
- Deciders: CTO, Principal Quant Researcher, Database Architect
- Related: ADR-0012

## Context

The charter fixes a specific tradable set (AAPL, MSFT, …, GE) and a separate
analysis-only set (S&P 500, Nasdaq-100, …, VIX), and mandates: "Store the
universe in the database. Never hardcode symbols," and "Do not generate trades
directly from the indices." This must be an enforced architectural rule, not a
convention, so future contributors cannot accidentally violate it.

## Options considered

**A. Hard-coded constants.** Rejected by the charter outright. Brittle,
requires a redeploy to change, and impossible to audit per-environment.

**B. Config file (YAML/TOML) checked into the repo.** Better than code, but
still requires a redeploy and lives outside the auditable, queryable system of
record. Cannot easily express "this universe was active on date X."

**C. Database tables with effective dating (chosen).** Universes are first-class
rows: instruments, named universes, and membership rows (optionally
date-ranged). Adding a symbol is an `INSERT`. Indices carry `is_index = true`
and are blocked at the signal boundary. Chosen.

## Decision

Model universes in PostgreSQL:
- `instrument` — one row per tradable/observable asset, with `asset_class`,
  `sector`, and `is_index` flags.
- `universe` — a named collection (e.g., `default`, `analysis_indices`).
- `universe_membership` — many-to-many, optionally `effective_from`/`effective_to`.

The default trading universe is **seeded** from the charter; everything else
is runtime data. A runtime guard rejects any tradeable signal whose instrument
has `is_index = true`.

## Consequences

**Positive**
- Adding/removing symbols is a data change, not a code change or deploy.
- Full history: we can reconstruct "what was the universe on 2026-03-01."
- Indices-cannot-trade is enforced structurally, not by convention.
- Multiple named universes (e.g., a dev/test subset) coexist cleanly.

**Negative**
- Slightly more schema; migrations must keep the seed idempotent.
- Code that "knows" a symbol must always resolve it through the instrument
  table, never assume a constant.

**Neutral**
- The seed is part of Phase 3 (Database Design), reviewed like code.
