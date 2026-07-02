"""Stage 3 — Probability Calibration.

The Stage 1 LightGBM produces probability-like scores, but they're not truly calibrated:
if the model outputs 0.7, it doesn't mean 70% of those transactions are fraud in reality.
Isotonic regression fits a monotone map from raw score → calibrated probability
using a held-out validation set.

Once calibrated, downstream cost-sensitive decisions ("block if expected loss > $X")
become defensible. Uncalibrated scores can't support that math honestly.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression

log = logging.getLogger(__name__)


class IsotonicCalibrator:
    """Wraps sklearn's IsotonicRegression with a clean fit/transform API.

    Fitted on validation-set scores (not train — we need un-seen data to learn
    the correct mapping). Applied on any subsequent scores.
    """

    def __init__(self, out_of_bounds: str = "clip"):
        self.iso = IsotonicRegression(out_of_bounds=out_of_bounds)
        self.fitted = False

    def fit(self, y_score: np.ndarray, y_true: np.ndarray) -> "IsotonicCalibrator":
        """Fit isotonic mapping from raw score → calibrated probability."""
        y_score = np.asarray(y_score).astype(float)
        y_true = np.asarray(y_true).astype(int)
        self.iso.fit(y_score, y_true)
        self.fitted = True
        log.info("Isotonic calibrator fitted on %d val samples", len(y_score))
        return self

    def transform(self, y_score: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("Calibrator not fitted. Call .fit() first.")
        return self.iso.predict(np.asarray(y_score).astype(float))

    def fit_transform(self, y_score, y_true) -> np.ndarray:
        self.fit(y_score, y_true)
        return self.transform(y_score)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.iso, f)
        log.info("Saved calibrator to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "IsotonicCalibrator":
        with open(path, "rb") as f:
            iso = pickle.load(f)
        obj = cls()
        obj.iso = iso
        obj.fitted = True
        return obj
