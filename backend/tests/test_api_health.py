"""Integration test: the FastAPI app boots and health endpoints respond.

Uses FastAPI's test client — no Docker needed, but it exercises the real app
factory, middleware (correlation id), and exception handler.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_ready_ok(client: TestClient):
    assert client.get("/ready").status_code == 200


def test_correlation_id_echoed(client: TestClient):
    r = client.get("/health", headers={"x-correlation-id": "cid-xyz"})
    assert r.headers["x-correlation-id"] == "cid-xyz"


def test_correlation_id_generated_when_absent(client: TestClient):
    r = client.get("/health")
    assert r.headers["x-correlation-id"]  # server generated one


def test_openapi_published(client: TestClient):
    # The contract surface must be discoverable.
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
