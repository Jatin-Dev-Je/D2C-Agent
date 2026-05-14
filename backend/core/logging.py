from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import Processor

from backend.core.config import get_settings


# ---------------------------------------------------
# Request / Trace Context
# ---------------------------------------------------

request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)

merchant_id_context: ContextVar[str | None] = ContextVar(
    "merchant_id",
    default=None,
)


# ---------------------------------------------------
# Context Injection Processor
# ---------------------------------------------------

def add_runtime_context(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Inject runtime tracing context into all log events.

    This enables:
    - request correlation
    - merchant tracing
    - distributed debugging
    - AI execution visibility
    """

    request_id = request_id_context.get()

    merchant_id = merchant_id_context.get()

    if request_id:
        event_dict["request_id"] = request_id

    if merchant_id:
        event_dict["merchant_id"] = merchant_id

    return event_dict


# ---------------------------------------------------
# Logging Configuration
# ---------------------------------------------------

def configure_logging() -> None:
    """
    Configure application-wide structured logging.

    Development:
    - pretty console logs
    - colors
    - readable tracebacks

    Production:
    - JSON logs
    - machine-readable
    - ingestion-safe
    """

    settings = get_settings()

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_runtime_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(
            fmt="iso",
            utc=True,
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_production:
        renderer: Processor = structlog.processors.JSONRenderer()

    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(
            file=sys.stdout,
        ),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )


# ---------------------------------------------------
# Logger Helper
# ---------------------------------------------------

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return structured application logger.
    """

    return structlog.get_logger(name)


# ---------------------------------------------------
# Runtime Context Helpers
# ---------------------------------------------------

def bind_request_id(request_id: str) -> None:
    """
    Bind request ID to runtime context.
    """

    request_id_context.set(request_id)


def bind_merchant_id(merchant_id: str) -> None:
    """
    Bind merchant ID to runtime context.
    """

    merchant_id_context.set(merchant_id)


def clear_runtime_context() -> None:
    """
    Prevent context leakage between requests.
    """

    request_id_context.set(None)

    merchant_id_context.set(None)