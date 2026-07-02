"""Model service: loads trained artifacts at startup and provides scoring + SHAP.

This is a singleton — one instance shared across the whole FastAPI app.
Model is loaded ONCE at startup (not on every request), so the /predict
latency is dominated by feature building + one LightGBM predict call.

Design:
  - Stage 1 LightGBM produces raw scores
  - Stage 3 Isotonic Calibrator maps raw scores to calibrated probabilities
  - LightGBM's native pred_contrib gives us SHAP values (fast, exact, no
    additivity issues on categorical features)
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from api.config import get_settings
from chimera_fd.features.engineering import get_feature_columns
from chimera_fd.models.calibration import IsotonicCalibrator
from chimera_fd.models.stage1_lightgbm import Stage1LightGBM

log = logging.getLogger(__name__)
settings = get_settings()


class ModelService:
    """Singleton model service. Access via get_model_service()."""

    _instance: Optional["ModelService"] = None

    def __init__(self):
        self.stage1: Optional[Stage1LightGBM] = None
        self.calibrator: Optional[IsotonicCalibrator] = None
        self.feature_columns: list[str] = []
        self.model_version: str = "unknown"
        self.loaded: bool = False

    def load(self) -> "ModelService":
        """Load all artifacts. Idempotent — safe to call twice."""
        if self.loaded:
            return self

        # Stage 1 LightGBM
        s1_path = settings.stage1_model_path
        if not s1_path.exists():
            raise FileNotFoundError(f"Stage 1 model not found: {s1_path}")
        log.info("Loading Stage 1 model from %s", s1_path)
        self.stage1 = Stage1LightGBM.load(s1_path)
        self.feature_columns = self.stage1.feature_names
        self.model_version = f"stage1_lightgbm@{s1_path.stat().st_mtime_ns}"
        log.info("Stage 1 loaded: %d features, best_iteration=%d",
                 len(self.feature_columns), self.stage1.model.best_iteration)

        # Stage 3 Calibrator (optional but expected)
        s3_path = settings.stage3_calibrator_path
        if s3_path.exists():
            log.info("Loading Stage 3 calibrator from %s", s3_path)
            self.calibrator = IsotonicCalibrator.load(s3_path)
            log.info("Stage 3 calibrator loaded.")
        else:
            log.warning("Stage 3 calibrator not found at %s — will return raw scores only", s3_path)

        self.loaded = True
        return self

    def warmup(self):
        """Run one dummy prediction so LightGBM JIT-caches, avoiding cold-start."""
        if not self.loaded:
            self.load()
        log.info("Warming up model with dummy prediction...")
        dummy = pd.DataFrame([{c: 0.0 for c in self.feature_columns}])
        _ = self.score(dummy)
        log.info("Warmup complete.")

    def score(self, X: pd.DataFrame) -> dict:
        """Score one or more transactions.

        Args:
            X: DataFrame with the same columns as training features. Missing
               columns get 0, extra columns are ignored.

        Returns:
            dict with:
              - raw_scores:        np.array of raw LightGBM probabilities
              - calibrated_scores: np.array of calibrated probs (or copy of raw)
              - decisions:         list of "approve" | "review" | "block"
              - latency_ms:        milliseconds spent in scoring
        """
        if not self.loaded:
            self.load()

        # Ensure X has the exact columns the model was trained on
        X_use = self._align_columns(X)

        t0 = time.time()
        raw = self.stage1.predict_proba(X_use)
        raw = np.asarray(raw, dtype=float)

        if self.calibrator is not None:
            calibrated = self.calibrator.transform(raw)
        else:
            calibrated = raw.copy()

        decisions = [self._decide(p) for p in calibrated]
        latency_ms = (time.time() - t0) * 1000

        return {
            "raw_scores": raw,
            "calibrated_scores": calibrated,
            "decisions": decisions,
            "latency_ms": latency_ms,
        }

    def shap(self, X: pd.DataFrame, top_k: int = 5) -> list[dict]:
        """Return SHAP top-K contributing features for each row.

        Uses LightGBM's native pred_contrib for exact, fast values.
        Returns a list (one entry per row) of dicts:
          [{"feature": "amt", "value": 500.0, "contribution": +1.23}, ...]
        """
        if not self.loaded:
            self.load()

        X_use = self._align_columns(X)
        contribs = self.stage1.model.predict(
            X_use, pred_contrib=True,
            num_iteration=self.stage1.model.best_iteration,
        )
        contribs = np.asarray(contribs)
        # Last column is bias; drop it
        contribs = contribs[:, :-1]

        out = []
        for row_idx in range(len(X_use)):
            vals = contribs[row_idx]
            # top-k by absolute contribution
            top_indices = np.argsort(-np.abs(vals))[:top_k]
            entries = []
            for i in top_indices:
                feat = self.feature_columns[i]
                entries.append({
                    "feature": feat,
                    "value": _safe_scalar(X_use.iloc[row_idx][feat]),
                    "contribution": float(vals[i]),
                })
            out.append(entries)
        return out

    def _align_columns(self, X: pd.DataFrame) -> pd.DataFrame:
        """Ensure X has exactly self.feature_columns. Fill missing with 0."""
        missing = set(self.feature_columns) - set(X.columns)
        if missing:
            for c in missing:
                X = X.copy()
                X[c] = 0
        return X[self.feature_columns]

    def _decide(self, prob: float) -> str:
        if prob < settings.approve_below:
            return "approve"
        if prob > settings.block_above:
            return "block"
        return "review"


def _safe_scalar(v):
    """Convert numpy/pandas scalars to plain Python for JSON serialization."""
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return str(v)
    return v


# ---- Singleton accessor ----
def get_model_service() -> ModelService:
    if ModelService._instance is None:
        ModelService._instance = ModelService()
    return ModelService._instance
