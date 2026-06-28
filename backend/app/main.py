"""FastAPI application factory (ADR-0001, ADR-0008, ADR-0009).

Phase 1 ships a minimal but production-shaped app shell:
- structured logging with a per-request correlation id;
- a global exception handler that never leaks internals;
- ``/health`` (liveness) and ``/ready`` (readiness, checks infra deps).

Bounded-context routers (market_data, risk, trading, ...) are mounted in
later phases. Their absence now is intentional — Phase 1 is the topology
skeleton, not feature code.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.logging import bind_context, clear_context, configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Configure logging once at startup (idempotent)."""
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    log = get_logger("app.bootstrap")
    log.info(
        "application_starting",
        env=settings.env,
        app=settings.name,
        version=__version__,
    )
    yield
    log.info("application_stopping", app=settings.name)


def create_app() -> FastAPI:
    """Build the configured FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="Quant Platform API",
        description="Institutional AI Quant Research & Trading Platform",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Stamp every request with a correlation id and bind it to logs."""
        cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex
        bind_context(correlation_id=cid, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            clear_context()
        response.headers["x-correlation-id"] = cid
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        """Translate any uncaught exception into a safe 500 — no internals leaked."""
        log = get_logger("app.errors")
        log.exception("unhandled_exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error"},
            headers={"x-correlation-id": request.headers.get("x-correlation-id", "")},
        )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        """Liveness probe — the process is up."""
        return {"status": "ok", "version": __version__, "env": settings.env}

    @app.get("/ready", tags=["meta"])
    async def readiness() -> dict[str, str]:
        """Readiness probe — dependencies are reachable.

        Phase 1: returns ok unconditionally; later phases add real checks
        (DB ping, Redis ping) via a ``ReadinessProbe`` port.
        """
        return {"status": "ready"}

    return app


app = create_app()
