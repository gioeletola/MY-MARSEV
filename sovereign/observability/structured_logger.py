"""
Structured logging configuration for the SOVEREIGN AI OS.

Uses structlog for consistent, machine-readable log output.
  - Development: colourised key-value console output
  - Production:  JSON lines to stdout (set json_output=True)
"""
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO", json_output: bool = False) -> None:
    """
    Configure structlog for the entire application.

    Call once at startup (in bootstrap.py) before any other imports.

    Args:
        log_level:   Standard Python log level string (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, emit JSON lines to stdout (production mode).
                     If False, emit human-readable colourised output (dev mode).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_output:
        structlog.processors.JSONRenderer()
    else:
        structlog.dev.ConsoleRenderer(colors=True)  # type: ignore[assignment]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so that third-party libraries (httpx, anthropic)
    # route through structlog.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a bound structlog logger pre-tagged with the module name."""
    return structlog.get_logger(name)
