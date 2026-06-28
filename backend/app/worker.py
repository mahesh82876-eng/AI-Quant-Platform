"""Celery application factory (ADR-0003).

Celery is the async workhorse for ingestion, backtests, training, and
continuous risk. Tasks are thin orchestrators over the domain — they contain
no business logic. Phase 1 wires only the broker/backend and a single
``ping`` task that proves the topology end-to-end; real tasks arrive with
their owning phase (e.g., ingestion in Phase 6, backtests in Phase 11).
"""

from __future__ import annotations

from celery import Celery
from celery.signals import task_postrun, task_prerun

from app.config import get_settings
from app.logging import bind_context, clear_context, configure_logging


def create_celery() -> Celery:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    app = Celery(
        "quant_platform",
        broker=settings.redis.url,
        backend=settings.redis.url,
        include=["app.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        # Route by workload class once per-queue workers exist (later phases).
        task_default_queue="default",
    )
    return app


celery_app = create_celery()


# ---- Correlation propagation across task boundaries (ADR-0008) ----
@task_prerun.connect
def _bind_task_context(task_id: str, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
    bind_context(task_id=task_id)


@task_postrun.connect
def _clear_task_context(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
    clear_context()
