# Backend — Quant Platform

Python backend: FastAPI API + Celery workers + the pure quant domain.

See [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the system design and
[`../ROADMAP.md`](../ROADMAP.md) for the build order.

## Local dev (no Docker)

```bash
pip install -e ".[dev]"
pytest                      # run tests
ruff check app tests        # lint
mypy app                    # type-check
uvicorn app.main:app --reload
```

## Local dev (Docker, full stack)

From the repo root:

```bash
make up            # postgres + redis + api + worker + beat
make health        # → http://localhost:8000/health
make celery-ping   # round-trip a task
make down
```

## Layout (Phase 1)

```
app/
├── __init__.py
├── config.py     # typed settings (ADR-0009)
├── logging.py    # structlog + secret redaction (ADR-0008)
├── main.py       # FastAPI app factory
├── worker.py     # Celery app factory
└── tasks.py      # task registry (Phase 1: ping only)
tests/            # unit (no infra) + integration markers
```

Bounded-context packages (`market_data`, `risk`, `trading`, …) are added in
their owning phases. None exist yet — Phase 1 is the topology skeleton only.
