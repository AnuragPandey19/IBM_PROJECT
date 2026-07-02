"""Health check endpoints. Used by load balancers, Docker healthchecks,
Kubernetes probes, monitoring systems."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import Settings, get_settings
from api.db.session import get_db

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
