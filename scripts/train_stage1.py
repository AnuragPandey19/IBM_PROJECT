"""Train Stage 1 LightGBM baseline.

Loads engineered parquet → trains LightGBM with early stopping → evaluates on val + test
→ saves model + evaluation report.

Usage:
    python scripts/train_stage1.py
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from chimera_fd.config import load_config
from chimera_fd.data.loader import load_parquet
from chimera_fd.evaluation.metrics import evaluate, find_best_threshold
from chimera_fd.features.engineering import get_feature_columns
from chimera_fd.models.stage1_lightgbm import LightGBMConfig, Stage1LightGBM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_stage1")


def main():
    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "ieee_cis"
    models_dir = ROOT / "models"
    reports_dir = ROOT / "reports"
    models_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    t0 = time.time()

    log.info("Loading engineered splits...")
    train = load_parquet(processed / "train_features.parquet")
    val = load_parquet(processed / "val_features.parquet")
    test = load_parquet(processed / "test_features.parquet")
    log.info("Loaded: train=%s, val=%s, test=%s", train.shape, val.shape, test.shape)

    # Get feature columns (deterministic list — same as saved during build_features)
    feat_cols = get_feature_columns(train)
    log.info("Feature columns: %d", len(feat_cols))

    X_train, y_train = train[feat_cols], train["isFraud"].values
    X_val, y_val = val[feat_cols], val["isFraud"].values
    X_test, y_test = test[feat_cols], test["isFraud"].values

    # Build config from YAML
    m_cfg = cfg.model.stage1
    trainer_cfg = LightGBMConfig(
        num_boost_round=int(m_cfg.num_boost_round),
        early_stopping_rounds=int(m_cfg.early_stopping_rounds),
        scale_pos_weight=m_cfg.scale_pos_weight,
        params=dict(m_cfg.params) if hasattr(m_cfg, "params") else None,
    )

    log.info("=" * 60)
    log.info("Training Stage 1 LightGBM")
    log.info("=" * 60)
    trainer = Stage1LightGBM(cfg=trainer_cfg)
    trainer.fit(X_train, y_train, X_val, y_val)

    log.info("=" * 60)
    log.info("Evaluating on VALIDATION set")
    log.info("=" * 60)
    val_score = trainer.predict_proba(X_val)
    best_thresh = find_best_threshold(y_val, val_score)
    val_report = evaluate(y_val, val_score, threshold=best_thresh)
    log.info("VAL metrics:\n%s", val_report.summary())

    log.info("=" * 60)
    log.info("Evaluating on TEST set (using threshold picked from VAL)")
    log.info("=" * 60)
    test_score = trainer.predict_proba(X_test)
    test_report = evaluate(y_test, test_score, threshold=best_thresh)
    log.info("TEST metrics:\n%s", test_report.summary())

    # Feature importance (top 30)
    imp = trainer.feature_importance("gain")
    log.info("Top 30 features by GAIN importance:\n%s", imp.head(30).to_string(index=False))

    # Save
    trainer.save(models_dir / "stage1_lightgbm.pkl")
    log.info("Model saved: %s", models_dir / "stage1_lightgbm.pkl")

    # Save evaluation JSON
    report_json = {
        "val": val_report.as_dict(),
        "test": test_report.as_dict(),
        "chosen_threshold_from_val": best_thresh,
        "training_time_seconds": round(time.time() - t0, 1),
        "n_features": len(feat_cols),
        "best_iteration": trainer.model.best_iteration,
    }
    with open(reports_dir / "stage1_evaluation.json", "w") as f:
        json.dump(report_json, f, indent=2)
    log.info("Evaluation JSON: %s", reports_dir / "stage1_evaluation.json")

    # Save feature importance CSV
    imp.to_csv(reports_dir / "stage1_feature_importance.csv", index=False)
    log.info("Feature importance CSV: %s", reports_dir / "stage1_feature_importance.csv")

    log.info("=" * 60)
    log.info("STAGE 1 TRAINING COMPLETE — total time %.1f seconds", time.time() - t0)
    log.info("=" * 60)
    log.info("HEADLINE NUMBERS:")
    log.info("  VAL  PR-AUC = %.4f  |  ROC-AUC = %.4f", val_report.pr_auc, val_report.roc_auc)
    log.info("  TEST PR-AUC = %.4f  |  ROC-AUC = %.4f", test_report.pr_auc, test_report.roc_auc)
    log.info("  TEST Precision @ 50%% Recall = %.4f", test_report.precision_at_50_recall)
    log.info("  TEST Recall    @ 5%%  FPR    = %.4f", test_report.recall_at_5pct_fpr)


if __name__ == "__main__":
    main()
