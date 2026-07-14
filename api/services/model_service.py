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
    """Singleton model service. Access via get_model_service().

    Loads TWO models:
      - IEEE-CIS Stage 1 LightGBM + Stage 3 isotonic calibrator (primary)
      - Sparkov Stage 1 LightGBM (interpretable-features demo model)

    Both are LightGBM under the hood but were trained on completely different
    feature spaces. Public API disambiguates via the `dataset` argument.
    """

    _instance: Optional["ModelService"] = None

    def __init__(self):
        # IEEE-CIS
        self.stage1: Optional[Stage1LightGBM] = None
        self.calibrator: Optional[IsotonicCalibrator] = None
        self.feature_columns: list[str] = []
        self.model_version: str = "unknown"

        # Sparkov
        self.sparkov_model: Optional[Stage1LightGBM] = None
        self.sparkov_feature_columns: list[str] = []
        self.sparkov_model_version: str = "unknown"

        self.loaded: bool = False

    def load(self) -> "ModelService":
        """Load all artifacts. Idempotent — safe to call twice."""
        if self.loaded:
            return self

        # ---- IEEE-CIS Stage 1 LightGBM ----
        s1_path = settings.stage1_model_path
        if not s1_path.exists():
            raise FileNotFoundError(f"Stage 1 model not found: {s1_path}")
        log.info("Loading IEEE-CIS Stage 1 from %s", s1_path)
        self.stage1 = Stage1LightGBM.load(s1_path)
        self.feature_columns = self.stage1.feature_names
        self.model_version = f"stage1_lightgbm@{s1_path.stat().st_mtime_ns}"
        log.info("IEEE-CIS Stage 1 loaded: %d features, best_iteration=%d",
                 len(self.feature_columns), self.stage1.model.best_iteration)

        # ---- Stage 3 Calibrator (IEEE-CIS only) ----
        s3_path = settings.stage3_calibrator_path
        if s3_path.exists():
            log.info("Loading Stage 3 calibrator from %s", s3_path)
            self.calibrator = IsotonicCalibrator.load(s3_path)
            log.info("Stage 3 calibrator loaded.")
        else:
            log.warning("Stage 3 calibrator not found at %s — will return raw scores only", s3_path)

        # ---- Sparkov Stage 1 LightGBM (optional — demo model) ----
        sp_path = settings.stage1_sparkov_path
        if sp_path.exists():
            log.info("Loading Sparkov Stage 1 from %s", sp_path)
            try:
                self.sparkov_model = Stage1LightGBM.load(sp_path)
                self.sparkov_feature_columns = self.sparkov_model.feature_names
                self.sparkov_model_version = f"stage1_sparkov@{sp_path.stat().st_mtime_ns}"
                log.info("Sparkov Stage 1 loaded: %d features, best_iteration=%d",
                         len(self.sparkov_feature_columns),
                         self.sparkov_model.model.best_iteration)
            except Exception as e:
                log.warning("Sparkov model load failed: %s — Sparkov endpoints will 503", e)
                self.sparkov_model = None
        else:
            log.warning("Sparkov model not found at %s — Sparkov endpoints will 503", sp_path)

        self.loaded = True
        return self

    def warmup(self):
        """Run one dummy prediction so LightGBM JIT-caches, avoiding cold-start."""
        if not self.loaded:
            self.load()
        log.info("Warming up IEEE-CIS model with dummy prediction...")
        dummy = pd.DataFrame([{c: 0.0 for c in self.feature_columns}])
        _ = self.score(dummy)
        if self.sparkov_model is not None:
            log.info("Warming up Sparkov model with dummy prediction...")
            dummy_sp = pd.DataFrame([{c: 0.0 for c in self.sparkov_feature_columns}])
            _ = self.score_sparkov(dummy_sp)
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

    # ------------------------------------------------------------------
    # Sparkov-specific methods (parallel to score/shap but for Sparkov model)
    # ------------------------------------------------------------------
    #
    # Sparkov's fraud rate is ~0.24-0.49% (much lower than IEEE-CIS) so its
    # score distribution sits at much lower absolute values. The IEEE-CIS
    # thresholds (0.05 approve / 0.95 block) would route every Sparkov
    # transaction to "approve" — that defeats the demo.
    #
    # Chosen threshold from Sparkov val: 0.0115. We use:
    #   approve if p < 0.005 (well below the chosen threshold)
    #   block   if p > 0.05  (~4x the chosen threshold — high confidence)
    #   review otherwise
    # ------------------------------------------------------------------

    # Widened APPROVE band from 0.005 to 0.010 so that clearly-legit
    # transactions (small amount + established customer + business hours)
    # cleanly pass instead of drifting into the REVIEW zone due to minor
    # feature noise. Block threshold unchanged — genuine fraud patterns are
    # still caught.
    _SPARKOV_APPROVE_BELOW = 0.010
    _SPARKOV_BLOCK_ABOVE = 0.05

    # Small-amount safety net: real payment gateways never auto-BLOCK on a
    # single low-value transaction — the correct fraud response is to
    # step-up (OTP / 3DS) into REVIEW instead. This matches how card
    # testing is actually detected — through VELOCITY across many rapid
    # attempts, not a single small isolated purchase. Prevents the demo
    # from over-blocking legitimate late-night hostel / worker orders.
    _SPARKOV_SMALL_AMOUNT_MAX_BLOCK_USD = 12.0   # ~ ₹960 at ₹80/USD

    def score_sparkov(self, X: pd.DataFrame) -> dict:
        """Score using the Sparkov Stage 1 model.

        No calibration layer for Sparkov — the raw LightGBM probabilities are
        already well calibrated (Brier=0.002, ECE=0.002 on test).
        """
        if not self.loaded:
            self.load()
        if self.sparkov_model is None:
            raise RuntimeError("Sparkov model is not loaded on this server")

        X_use = self._align_sparkov_columns(X)

        t0 = time.time()
        raw = self.sparkov_model.predict_proba(X_use)
        raw = np.asarray(raw, dtype=float)
        # No calibrator — Sparkov model is already well-calibrated
        calibrated = raw.copy()

        # Extract amt column for the small-amount safety net (best-effort).
        # If amt column is missing (should never happen in Sparkov mode) we
        # fall back to treating every row as normal.
        amts = None
        if "amt" in X_use.columns:
            amts = np.asarray(X_use["amt"].values, dtype=float)

        decisions = []
        for i, p in enumerate(calibrated):
            amt_i = float(amts[i]) if amts is not None else None
            decisions.append(self._decide_sparkov(p, amt_i))
        latency_ms = (time.time() - t0) * 1000

        return {
            "raw_scores": raw,
            "calibrated_scores": calibrated,
            "decisions": decisions,
            "latency_ms": latency_ms,
        }

    def shap_sparkov(self, X: pd.DataFrame, top_k: int = 5) -> list[dict]:
        """SHAP top-K contributions for Sparkov model. Same logic as `shap`
        but against the Sparkov booster + feature space."""
        if not self.loaded:
            self.load()
        if self.sparkov_model is None:
            raise RuntimeError("Sparkov model is not loaded on this server")

        X_use = self._align_sparkov_columns(X)
        contribs = self.sparkov_model.model.predict(
            X_use, pred_contrib=True,
            num_iteration=self.sparkov_model.model.best_iteration,
        )
        contribs = np.asarray(contribs)
        contribs = contribs[:, :-1]  # drop bias column

        out = []
        for row_idx in range(len(X_use)):
            vals = contribs[row_idx]
            top_indices = np.argsort(-np.abs(vals))[:top_k]
            entries = []
            for i in top_indices:
                feat = self.sparkov_feature_columns[i]
                entries.append({
                    "feature": feat,
                    "value": _safe_scalar(X_use.iloc[row_idx][feat]),
                    "contribution": float(vals[i]),
                })
            out.append(entries)
        return out

    def _align_sparkov_columns(self, X: pd.DataFrame) -> pd.DataFrame:
        """Same as _align_columns but against the Sparkov feature list."""
        missing = set(self.sparkov_feature_columns) - set(X.columns)
        if missing:
            X = X.copy()
            for c in missing:
                X[c] = 0
        return X[self.sparkov_feature_columns]

    def _decide_sparkov(self, prob: float, amt: Optional[float] = None) -> str:
        # Safety net: never auto-BLOCK a very small isolated transaction.
        # Real card-testing detection is a velocity problem (many small
        # attempts in a burst), not a single low-value purchase — a hostel
        # student ordering ₹320 groceries at midnight should not be blocked.
        # For amounts below the small-amount threshold, the strongest action
        # is REVIEW (step-up verification / OTP).
        if (
            amt is not None
            and amt <= self._SPARKOV_SMALL_AMOUNT_MAX_BLOCK_USD
            and prob > self._SPARKOV_BLOCK_ABOVE
        ):
            return "review"

        if prob < self._SPARKOV_APPROVE_BELOW:
            return "approve"
        if prob > self._SPARKOV_BLOCK_ABOVE:
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
