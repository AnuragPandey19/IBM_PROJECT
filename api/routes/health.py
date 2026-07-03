"""Health check endpoints. Used by load balancers, Docker healthchecks,
Kubernetes probes, monitoring systems."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import Settings, get_settings
from api.db.session import get_db


# ==========================================================================
# Root-level router for endpoints outside the /health prefix.
# External uptime monitors expect a stable, short path (e.g. /ping).
# ==========================================================================
root_router = APIRouter(tags=["monitor"])


@root_router.get(
    "/ping",
    response_class=PlainTextResponse,
    summary="Uptime monitor endpoint (plain text, no dependencies)",
)
def ping():
    """Ultra-lightweight liveness endpoint for external uptime monitors
    such as Uptime Robot, Better Stack, Pingdom, and StatusCake.

    Returns the plain text string "OK" with HTTP 200 and headers that
    disable caching. No authentication, no database queries, no model
    checks — this is a pure "is the ASGI server responsive?" probe.

    Guarantees:
      - Response body: 2 bytes ("OK")
      - Latency: sub-millisecond
      - No CORS, auth, cookies, or query dependencies
      - Deterministic response on every call
    """
    return PlainTextResponse(
        content="OK",
        status_code=200,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Robots-Tag": "noindex",
        },
    )


# ==========================================================================
# /health prefix router — richer health information for internal callers.
# ==========================================================================
router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check(cfg: Settings = Depends(get_settings)):
    """Basic liveness — 'is the app alive?'  Always fast, no DB check."""
    return {
        "status": "ok",
        "app": cfg.app_name,
        "version": cfg.app_version,
        "env": cfg.env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
def readiness_check(
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings),
):
    """Readiness — 'is the app ready to serve traffic?'  Checks DB + model files."""
    checks = {}

    # DB check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"fail: {type(e).__name__}"

    # Model files
    checks["stage1_model"] = "ok" if cfg.stage1_model_path.exists() else "missing"
    checks["stage3_calibrator"] = "ok" if cfg.stage3_calibrator_path.exists() else "missing"
    checks["feature_pipeline"] = "ok" if cfg.feature_pipeline_path.exists() else "missing"

    ok = all(v == "ok" for v in checks.values())
    return {
        "ready": ok,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
