"""Very small in-memory per-IP rate limiter.

Not intended to be a full-featured limiter (that's what `slowapi` or
`fastapi-limiter` are for). This exists so we can protect public endpoints
like `/api/checkout` on a single-container deployment without adding a
Redis dependency for the demo.

Usage::

    from api.dependencies.rate_limit import rate_limit

    @router.post("/api/checkout")
    def checkout(_: None = Depends(rate_limit("checkout", per_ip=10, window_s=60))):
        ...

The limiter is process-local — if you scale to more than one worker or
container, use a distributed backend instead.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable, Deque, DefaultDict, Tuple

from fastapi import HTTPException, Request, status


_STATE: DefaultDict[Tuple[str, str], Deque[float]] = defaultdict(deque)
_LOCK = threading.Lock()


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For if HF Space sits behind a proxy (it does).
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client is not None:
        return request.client.host or "unknown"
    return "unknown"


def rate_limit(
    bucket: str,
    per_ip: int,
    window_s: float,
) -> Callable[[Request], None]:
    """FastAPI dependency factory. Enforces at most `per_ip` requests per
    `window_s` seconds per client IP for the named bucket."""

    def _dep(request: Request) -> None:
        ip = _client_ip(request)
        key = (bucket, ip)
        now = time.monotonic()
        cutoff = now - window_s

        with _LOCK:
            dq = _STATE[key]
            # Drop stale timestamps
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= per_ip:
                # Report how long until the oldest ping ages out
                retry_after = max(1, int(dq[0] + window_s - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Too many requests to {bucket!r}. "
                        f"Try again in {retry_after}s."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            dq.append(now)

    return _dep
