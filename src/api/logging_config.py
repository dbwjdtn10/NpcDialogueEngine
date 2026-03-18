"""Structured JSON logging configuration.

Produces machine-parseable JSON log lines suitable for log aggregation
systems (ELK, Loki, CloudWatch, etc.) while keeping human-readable
fallback for local development.

Usage::

    from src.api.logging_config import setup_logging
    setup_logging()  # Call once at application startup

Environment variables:
    LOG_LEVEL   – root log level (default: INFO)
    LOG_FORMAT  – "json" for structured output, "text" for human-readable (default: json)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects.

    Output fields:
        timestamp, level, logger, message, module, function, line,
        plus any extras attached to the record (e.g. request_id).
    """

    # Fields that are part of the standard LogRecord and should not
    # appear in the ``extra`` bag.
    _BUILTIN_ATTRS = frozenset(
        logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
        | {"message", "asctime", "taskName"}
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Merge any extra context the caller attached
        for key, value in record.__dict__.items():
            if key not in self._BUILTIN_ATTRS and not key.startswith("_"):
                payload[key] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    """Configure the root logger based on environment variables.

    Call this once during application startup (before any log
    statements are executed).
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json").lower()

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers to avoid duplicate output
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root.addHandler(handler)

    # Quiet down noisy third-party loggers
    for noisy in ("uvicorn.access", "httpcore", "httpx", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
