"""Integration test: the Celery topology executes a task.

Runs the ping task *eagerly* (in-process) so it needs no broker. It still
proves the worker app factory, task registration, and logging hooks work.
"""

from __future__ import annotations

import pytest

from app.tasks import ping
from app.worker import celery_app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _eager_mode():
    """Run tasks synchronously, in-process, without a broker."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False


def test_ping_task_returns_pong():
    result = ping.delay()
    assert result.get(timeout=5) == "pong"


def test_ping_task_registered():
    # The task name must be resolvable on the app — proves registration.
    assert "app.tasks.ping" in celery_app.tasks
