"""Cross-dataset test — train Stage 1 on Sparkov using the same methodology.

Loads Sparkov CSV -> engineers features -> time-splits -> trains LightGBM with
same config as IEEE-CIS (no SMOTE, scale_pos_weight) -> evaluates -> reports
comparison to IEEE-CIS numbers.

Story: same methodology, different dataset. If PR-AUC is similar magnitude
(0.4-0.7), methodology generalizes.

Usage:
    python scripts/train_sparkov.py
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
from chimera_fd.data.loader import load_parquet, load_sparkov
from chimera_fd.data.splitter import time_based_split
from chimera_fd.evaluation.metrics import evaluate, find_best_threshold
from chimera_fd.features.sparkov_engineering import (
    SparkovFeaturePipeline,
    SPARKOV_LABEL_COLS,
    get_sparkov_feature_columns,
)
from chimera_fd.models.stage1_lightgbm import LightGBMConfig, Stage1LightGBM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_sparkov")


def main():
    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "sparkov"
    processed.mkdir(parents=True, exist_ok=True)
    models_dir = ROOT / "models"
    reports_dir = ROOT / "reports"

    t0 = time.time()

    # ------ Load raw Sparkov (train + test come pre-split, we merge and re-split) ------
    log.info("Loading Sparkov raw CSVs...")
    train_raw, test_raw = load_sparkov(
        cfg.data.sparkov.train,
        cfg.data.sparkov.test,
    )
    merged = pd.concat([train_raw, test_raw], axis=0, ignore_index=True)
    log.info("Merged Sparkov: %d rows. Fraud rate: %.3f%%",
             len(merged), 100 * merged["is_fraud"].mean())

    # ------ Time-based split (chronological — no random) ------
    train_df, val_df, test_df = time_based_split(
        merged, time_col="unix_time",
        train_frac=0.80, val_frac=0.10, test_frac=0.10,
    )

    # ------ Feature engineering (same principle: fit on train only) ------
    log.info("=" * 60)
    log.info("Feature engineering (fit on TRAIN only)")
    log.info("=" * 60)
    pipe = SparkovFeaturePipeline()
    pipe.fit(train_df)

    log.info("Transforming train...")
    train_ft = pipe.transform(train_df)
    log.info("Transforming val...")
    val_ft = pipe.transform(val_df)
    log.info("Transforming test...")
    test_ft = pipe.transform(test_df)

    # Save engineered parquet for reproducibility
    train_ft.to_parquet(processed / "train_features.parquet", index=False)
    val_ft.to_parquet(processed / "val_features.parquet", index=False)
    test_ft.to_parquet(processed / "test_features.parquet", index=False)
    log.info("Saved Sparkov engineered parquet to %s", processed)

    feat_cols = get_sparkov_feature_columns(train_ft)
    log.info("Usable feature columns: %d", len(feat_cols))
    log.info("First 15 features: %s", feat_cols[:15])

    X_train = train_ft[feat_cols]
    y_train = train_ft["is_fraud"].values
    X_val = val_ft[feat_cols]
    y_val = val_ft["is_fraud"].values
    X_test = test_ft[feat_cols]
    y_test = test_ft["is_fraud"].values

    # ------ Train LightGBM with SAME methodology as IEEE-CIS ------
    log.info("=" * 60)
    log.info("Training Sparkov LightGBM (same config as IEEE-CIS)")
    log.info("=" * 60)

    # Configure explicit categorical features for LightGBM
    cat_feats_present = [c for c in SPARKOV_LABEL_COLS if c in feat_cols]
    log.info("Categorical features for LightGBM: %s", cat_feats_present)

    trainer_cfg = LightGBMConfig(
        num_boost_round=2000,
        early_stopping_rounds=100,
        scale_pos_weight="auto",
    )
    trainer = Stage1LightGBM(cfg=trainer_cfg)
    # Override the categoricals since Sparkov has different columns
    trainer.categorical_features = cat_feats_present
    trainer._resolve_categorical = lambda X: cat_feats_present  # type: ignore
    trainer.fit(X_train, y_train, X_val, y_val)

    # ------ Evaluate ------
    log.info("=" * 60)
    log.info("Evaluating on VAL + TEST")
    log.info("=" * 60)
    val_score = trainer.predict_proba(X_val)
    test_score = trainer.predict_proba(X_test)

    val_report = evaluate(y_val, val_score)
    log.info("VAL metrics:\n%s", val_report.summary())

    best_thresh = find_best_threshold(y_val, val_score)
    test_report = evaluate(y_test, test_score, threshold=best_thresh)
    log.info("TEST metrics:\n%s", test_report.summary())

    # ------ Save ------
    trainer.save(models_dir / "stage1_sparkov.pkl")
    imp = trainer.feature_importance("gain")

    with open(reports_dir / "sparkov_evaluation.json", "w") as f:
        json.dump({
            "val": val_report.as_dict(),
            "test": test_report.as_dict(),
            "chosen_threshold_from_val": best_thresh,
            "training_time_seconds": round(time.time() - t0, 1),
            "n_features": len(feat_cols),
            "n_train_rows": len(train_ft),
            "n_val_rows": len(val_ft),
            "n_test_rows": len(test_ft),
            "top_10_features": imp.head(10).to_dict("records"),
        }, f, indent=2)
    imp.to_csv(reports_dir / "sparkov_feature_importance.csv", index=False)

    # ------ Cross-dataset comparison headline ------
    log.info("=" * 60)
    log.info("SPARKOV TRAINING COMPLETE - %.1f seconds", time.time() - t0)
    log.info("=" * 60)
    log.info("CROSS-DATASET COMPARISON (same methodology, two datasets):")
    log.info("  IEEE-CIS  TEST PR-AUC = 0.5036  (from stage1_evaluation.json)")
    log.info("  Sparkov   TEST PR-AUC = %.4f", test_report.pr_auc)
    log.info("  IEEE-CIS  TEST ROC-AUC = 0.8678")
    log.info("  Sparkov   TEST ROC-AUC = %.4f", test_report.roc_auc)
    log.info("")
    log.info("Top-10 features (gain importance):")
    for _, row in imp.head(10).iterrows():
        log.info("  %s : %.0f", row["feature"], row["importance"])


if __name__ == "__main__":
    main()
