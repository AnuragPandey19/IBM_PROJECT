"""HTTP middlewares that are shared across the app.

Right now: request-ID assignment. Kept separate from api/main.py so future
middlewares (auth logging, per-tenant metrics, etc.) have a home without main
becoming a wall of `@app.middleware` decorators.
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from api.logging_config import set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign every incoming request a UUID and echo it in the response.

    Honors an upstream `X-Request-ID` header when present (so tracing works
    across a proxy that already added one — e.g. HF Space's ingress).
    Otherwise generates a fresh UUID4.

    The ID is:
      - set on the current logging context so every log line carries it
      - returned as `X-Request-ID` on the response so clients / support can
        quote it back when reporting bugs
      - added as `X-Response-Time` in milliseconds — a cheap in-band way to
        surface backend latency without needing an APM.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        set_request_id(rid)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)

        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"
        return response
