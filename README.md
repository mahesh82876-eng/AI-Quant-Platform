# Institutional AI Quant Research & Trading Platform

An internal, hedge-fund-grade platform for market research, quantitative
analysis, machine learning, strategy research, backtesting, portfolio & risk
management, and paper/live trading.

> **Status:** Phase 1 — System Architecture (in progress)

This repository is being built phase-by-phase. See [`ROADMAP.md`](./ROADMAP.md)
for the full plan and [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the system
design. Never jump ahead: each phase must be approved before the next begins.

---

## Why this exists

Most "quant" projects collapse into a pile of notebooks and throwaway scripts.
This project is the opposite: a **maintainable, modular, testable platform**
that an engineering team can extend for years. Every decision optimizes for
maintainability, scalability, and code quality — not speed of generation.

## Engineering principles

- **Clean / Hexagonal Architecture** — the quant domain (strategies, risk,
  portfolio) is pure Python with no framework or I/O. External systems
  (brokers, data vendors, databases) are adapters behind interfaces.
- **SOLID & modular design** — each engine is a bounded context with a strict
  public interface; internals can be refactored or extracted to a service later.
- **Configuration over hard-coding** — the trading universe, risk limits, and
  credentials live in configuration and the database, never in source.
- **The Risk Engine is a non-bypassable enforcement point** — no order reaches
  a broker without passing a pre-trade risk check (see ADR-0006).
- **Realism by default** — every backtest accounts for commission, slippage,
  and latency. No cost-free fantasies.

## Tech stack (target)

| Layer        | Technology                                            |
| ------------ | ----------------------------------------------------- |
| Frontend     | Next.js, React, TypeScript, TailwindCSS, AG Grid, Recharts |
| Backend API  | Python, FastAPI, Pydantic v2                          |
| Async work   | Celery + Redis (broker/backend), Celery beat (cron)   |
| ML / Research| NumPy, Pandas, scikit-learn, XGBoost, LightGBM, PyTorch |
| Database     | PostgreSQL 16 + TimescaleDB (time-series), Redis 7    |
| Infra        | Docker, Docker Compose, GitHub Actions                |
| Cloud        | AWS-ready (no vendor lock-in in the core)             |

## Quickstart (Phase 1 skeleton)

```bash
cp .env.example .env          # then edit secrets
make up                       # postgres + redis + api + worker + beat
curl http://localhost:8000/health
make test                     # run the skeleton test suite
make down
```

`make help` lists all available commands.

## Repository layout (high level; detailed in Phase 2)

```
.
├── ARCHITECTURE.md          # system design, module map, data flows
├── ROADMAP.md               # 18-phase plan with exit criteria
├── docs/adr/                # Architecture Decision Records
├── docker-compose.yml       # local dev topology
├── infra/                   # Dockerfiles, k8s/terraform (later phases)
├── backend/                 # Python platform (FastAPI + Celery + domain)
└── frontend/                # Next.js dashboard (later phase)
```

## Phases

See [`ROADMAP.md`](./ROADMAP.md). The current phase is marked at the top of
this README. Work proceeds strictly in order.
