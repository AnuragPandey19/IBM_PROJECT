"""Fit isotonic calibration on val set → apply to val + test → report before/after.

Outputs:
  models/stage3_isotonic.pkl                 — fitted calibrator
  reports/calibration/reliability_before.png — reliability diagram, raw scores
  reports/calibration/reliability_after.png  — reliability diagram, calibrated
  reports/calibration/summary.json           — ECE + Brier before/after

Usage:
    python scripts/calibrate.py
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from chimera_fd.config import load_config
from chimera_fd.data.loader import load_parquet
from chimera_fd.evaluation.metrics import expected_calibration_error
from chimera_fd.models.calibration import IsotonicCalibrator
from chimera_fd.models.stage1_lightgbm import Stage1LightGBM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("calibrate")


def reliability_diagram(y_true, y_score, n_bins=10, title="Reliability Diagram"):
    """Bin predictions and plot bin_confidence vs bin_accuracy.
    A perfectly calibrated model traces the y=x diagonal.
    """
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    confidences, accuracies, weights = [], [], []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (y_score >= lo) & (y_score <= hi)
        else:
            mask = (y_score >= lo) & (y_score < hi)
        if not mask.any():
            confidences.append((lo + hi) / 2)
            accuracies.append(0)
            weights.append(0)
            continue
        confidences.append(float(y_score[mask].mean()))
        accuracies.append(float(y_true[mask].mean()))
        weights.append(mask.sum())

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Perfect calibration")
    ax.plot(confidences, accuracies, marker="o", linewidth=2, color="#c00000",
            label="Model")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted probability (bin mean)")
    ax.set_ylabel("Actual fraud rate")
    ax.set_title(title, fontweight="bold")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
    return fig


def main():
    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "ieee_cis"
    models_dir = ROOT / "models"
    out_dir = ROOT / "reports" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()

    log.info("Loading Stage 1 model...")
    model = Stage1LightGBM.load(models_dir / "stage1_lightgbm.pkl")

    log.info("Loading engineered val + test...")
    val = load_parquet(processed / "val_features.parquet")
    test = load_parquet(processed / "test_features.parquet")

    X_val = val[model.feature_names]
    y_val = val["isFraud"].values
    X_test = test[model.feature_names]
    y_test = test["isFraud"].values

    log.info("Scoring val + test (raw scores)...")
    val_raw = model.predict_proba(X_val)
    test_raw = model.predict_proba(X_test)

    # ---------- Before calibration ----------
    ece_val_before = expected_calibration_error(y_val, val_raw, n_bins=10)
    brier_val_before = brier_score_loss(y_val, val_raw)
    ece_test_before = expected_calibration_error(y_test, test_raw, n_bins=10)
    brier_test_before = brier_score_loss(y_test, test_raw)

    log.info("BEFORE calibration:")
    log.info("  VAL  ECE=%.4f  Brier=%.4f", ece_val_before, brier_val_before)
    log.info("  TEST ECE=%.4f  Brier=%.4f", ece_test_before, brier_test_before)

    fig = reliability_diagram(y_val, val_raw, title="Reliability BEFORE (VAL)")
    fig.savefig(out_dir / "reliability_before_val.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig = reliability_diagram(y_test, test_raw, title="Reliability BEFORE (TEST)")
    fig.savefig(out_dir / "reliability_before_test.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # ---------- Fit calibrator on VAL only ----------
    log.info("=" * 60)
    log.info("Fitting isotonic calibrator on VAL set")
    log.info("=" * 60)
    calib = IsotonicCalibrator()
    calib.fit(val_raw, y_val)
    calib.save(models_dir / "stage3_isotonic.pkl")

    val_cal = calib.transform(val_raw)
    test_cal = calib.transform(test_raw)

    ece_val_after = expected_calibration_error(y_val, val_cal, n_bins=10)
    brier_val_after = brier_score_loss(y_val, val_cal)
    ece_test_after = expected_calibration_error(y_test, test_cal, n_bins=10)
    brier_test_after = brier_score_loss(y_test, test_cal)

    log.info("AFTER calibration:")
    log.info("  VAL  ECE=%.4f  Brier=%.4f  (Δ ECE = %+.4f)",
             ece_val_after, brier_val_after, ece_val_after - ece_val_before)
    log.info("  TEST ECE=%.4f  Brier=%.4f  (Δ ECE = %+.4f)",
             ece_test_after, brier_test_after, ece_test_after - ece_test_before)

    fig = reliability_diagram(y_val, val_cal, title="Reliability AFTER (VAL)")
    fig.savefig(out_dir / "reliability_after_val.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig = reliability_diagram(y_test, test_cal, title="Reliability AFTER (TEST)")
    fig.savefig(out_dir / "reliability_after_test.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Save summary JSON
    summary = {
        "val": {
            "ece_before": ece_val_before,   "ece_after": ece_val_after,
            "brier_before": brier_val_before, "brier_after": brier_val_after,
            "ece_delta": ece_val_after - ece_val_before,
        },
        "test": {
            "ece_before": ece_test_before,   "ece_after": ece_test_after,
            "brier_before": brier_test_before, "brier_after": brier_test_after,
            "ece_delta": ece_test_after - ece_test_before,
        },
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    log.info("=" * 60)
    log.info("CALIBRATION COMPLETE in %.1f seconds", time.time() - t0)
    log.info("=" * 60)
    log.info("HEADLINE NUMBERS (calibration improvement):")
    log.info("  TEST ECE:   %.4f → %.4f  (%+.1f%% relative)",
             ece_test_before, ece_test_after,
             100 * (ece_test_after - ece_test_before) / ece_test_before)
    log.info("  TEST Brier: %.4f → %.4f  (%+.1f%% relative)",
             brier_test_before, brier_test_after,
             100 * (brier_test_after - brier_test_before) / brier_test_before)


if __name__ == "__main__":
    main()
