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


@root_router.api_route(
    "/ping",
    methods=["GET", "HEAD"],
    response_class=PlainTextResponse,
    summary="Uptime monitor endpoint (plain text, accepts GET and HEAD)",
)
def ping():
    """Ultra-lightweight liveness endpoint for external uptime monitors
    such as Uptime Robot, Better Stack, Pingdom, and StatusCake.

    Accepts both GET and HEAD methods — most monitors use HEAD by default
    to save bandwidth (no response body needed). Returns HTTP 200 with the
    plain text "OK" and cache-disabling headers.

    Guarantees:
      - Response body: 2 bytes ("OK") for GET, empty for HEAD
      - Latency: sub-millisecond
      - No auth, DB, or model dependencies
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


@router.api_route("", methods=["GET", "HEAD"])
def health_check(cfg: Settings = Depends(get_settings)):
    """Basic liveness — 'is the app alive?'  Always fast, no DB check.

    Accepts GET and HEAD (monitors often use HEAD).
    """
    return {
        "status": "ok",
        "app": cfg.app_name,
        "version": cfg.app_version,
        "env": cfg.env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.api_route("/ready", methods=["GET", "HEAD"])
def readiness_check(
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings),
):
    """Readiness — 'is the app ready to serve traffic?'  Checks DB + model files."""
    checks = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"fail: {type(e).__name__}"

    checks["stage1_model"] = "ok" if cfg.stage1_model_path.exists() else "missing"
    checks["stage3_calibrator"] = "ok" if cfg.stage3_calibrator_path.exists() else "missing"
    checks["feature_pipeline"] = "ok" if cfg.feature_pipeline_path.exists() else "missing"
    # Sparkov mode powers merchant portals + /api/checkout — treat as
    # first-class readiness signal, not an afterthought.
    checks["stage1_sparkov"] = "ok" if cfg.stage1_sparkov_path.exists() else "missing"
    checks["sparkov_features"] = "ok" if cfg.sparkov_features_path.exists() else "missing"

    ok = all(v == "ok" for v in checks.values())
    return {
        "ready": ok,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
