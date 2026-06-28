"""Structured logging configuration (ADR-0008).

Uses structlog with:
- a JSON renderer in staging/production, pretty console locally;
- a correlation-id processor so events can be traced across the API and workers;
- a secret-redaction processor so no SecretStr/key ever reaches a log sink.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

# Keys whose values must never be logged. Matched case-insensitively.
_REDACT_KEYS = frozenset(
    {
        "password",
        "secret",
        "api_key",
        "apikey",
        "api_secret",
        "token",
        "access_token",
        "refresh_token",
        "signing_key",
        "authorization",
    }
)

_CONFIGURED = False


def _redact_secrets(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Replace sensitive values with '***REDACTED***'."""

    def _scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: ("***REDACTED***" if k.lower() in _REDACT_KEYS else _scrub(v))
                    for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(_scrub(v) for v in value)
        return value

    scrubbed = _scrub(event_dict)
    return scrubbed if isinstance(scrubbed, dict) else dict(scrubbed)


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure structlog and stdlib logging exactly once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    # Shared processors for both foreign (stdlib) and structlog events.
    processors: list[structlog.typing.ProcessingFunction] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact_secrets,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )
    processors.append(renderer)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Route stdlib loggers (uvicorn, celery, sqlalchemy) through structlog.
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(message)s",
        stream=sys.stderr,
        force=True,
    )

    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def bind_context(**kwargs: Any) -> None:
    """Bind values (e.g., correlation_id, user_id) to the current context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear bound context (call at the end of a request/task)."""
    structlog.contextvars.clear_contextvars()
