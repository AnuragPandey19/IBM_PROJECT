"""Logging configuration.

Two modes, controlled by settings.env:

- dev:  human-friendly "TIMESTAMP [LEVEL] name: message" (grep-friendly at a
        terminal, easy to skim).
- prod: single-line JSON per record — the format HF Space, Render, Grafana
        Loki, Datadog etc. all expect. Includes request_id when set on the
        current request context so a single failing request can be traced
        across many log lines.

`request_id` is filled in by the RequestIdMiddleware (see api/middleware.py).
Nothing else in the app needs to know about it — every logger.info() call
picks it up automatically via the LogRecord filter installed here.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Optional


# Context variable that the request-id middleware sets on every incoming HTTP
# request. Log records emitted during that request pick it up via the filter.
# The default of `-` shows in startup logs and background tasks so the field
# is always present in JSON output (never null / missing).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    """Copy the current request_id into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line.

    Kept dependency-free (no python-json-logger). The fields match what
    Grafana / Loki auto-parse without extra config: `timestamp`, `level`,
    `logger`, `message`, `request_id`, plus any structured `extra=...` a
    caller passes.
    """

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "asctime", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # Include structured extras (anything passed via `extra={...}`) that
        # isn't a stdlib LogRecord attribute.
        for k, v in record.__dict__.items():
            if k in self._RESERVED or k == "request_id":
                continue
            try:
                json.dumps(v)  # cheap serializability check
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)

        return json.dumps(payload, default=str)


def configure_logging(env: str, log_level: str = "INFO") -> None:
    """Install the appropriate formatter + request-id filter on the root logger.

    Idempotent — safe to call at every process startup. Removes any existing
    handlers so uvicorn's default handlers don't double-print.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())

    if env == "prod":
        handler.setFormatter(_JsonFormatter())
    else:
        # Dev format — grep-friendly, includes request_id when present.
        handler.setFormatter(logging.Formatter(
            fmt=("%(asctime)s [%(levelname)s] %(name)s "
                 "[rid=%(request_id)s]: %(message)s"),
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silence noisy libraries at INFO but let their WARN+ through.
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def set_request_id(rid: str) -> None:
    """Called by the request-id middleware at the start of every request."""
    request_id_ctx.set(rid)


def get_request_id() -> Optional[str]:
    val = request_id_ctx.get()
    return None if val == "-" else val
