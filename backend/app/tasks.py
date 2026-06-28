"""Celery tasks.

Phase 1 exposes only a topology-proving ``ping``. Each later phase adds its
own tasks here (or in a per-context ``tasks.py``) — never in the domain.
"""

from __future__ import annotations

from app.logging import get_logger
from app.worker import celery_app

log = get_logger("app.tasks")


@celery_app.task(name="app.tasks.ping")
def ping() -> str:
    """Round-trip health task used by the smoke test and Docker healthcheck."""
    log.info("ping_task_executed")
    return "pong"
