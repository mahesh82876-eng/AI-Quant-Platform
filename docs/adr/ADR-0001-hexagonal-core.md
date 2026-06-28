# ADR-0001: Hexagonal architecture for the quant core

- Status: accepted
- Date: 2026-06-28
- Deciders: CTO, Principal Quant Researcher, Senior Backend Engineer
- Related: ADR-0005, ADR-0006, ADR-0007

## Context

A quant platform must outlive its first broker, its first database, and its
first author. If strategies, risk, and portfolio logic depend on a concrete
broker SDK or ORM, every infrastructure change forces a rewrite of the domain —
the most valuable and least stable part of the system. The project charter
explicitly demands a platform that "can be expanded for years" and that adding
Interactive Brokers later requires "minimal changes."

## Options considered

**A. Layered (traditional 3-tier).** UI → service → data-access. Simple, but
the domain leaks into the service layer and couples tightly to the DB and
frameworks. Refactors are expensive.

**B. Hexagonal / Ports & Adapters.** The domain is pure Python that talks only
to interfaces (ports). Brokers, DBs, vendors are adapters. Chosen.

**C. Microservices from day one.** Each engine a separate service. Maximally
decoupled but introduces network, deployment, and transactional complexity
before the domain is even proven. Premature.

**D. Notebook-first.** Rejected outright — violates the charter
("Don't create notebooks unless requested") and the anti-corruption rules.

## Decision

Adopt **hexagonal architecture**: the quant domain (strategies, signals, risk,
portfolio, backtesting event loop, features) is pure Python with zero
infrastructure imports. External systems are adapters behind ports.

## Consequences

**Positive**
- The domain is unit-testable with no Docker/Postgres/broker — fast, deterministic tests.
- New brokers/vendors are new adapters; the core never changes (ADR-0005).
- Strategies run identically in backtest and live (ADR-0007).

**Negative**
- More interfaces and indirection up front — a learning curve for new engineers.
- Slightly more code than a "just call the SDK" approach.

**Neutral**
- Adapters must be thin: translate external types ↔ domain contracts, nothing more.
