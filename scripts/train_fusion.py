"""Train the Fusion Head — combines Stage 1 LightGBM + Stage 2 GraphSAGE embeddings.

Loads:
  - Stage 1 model → predicts on train/val/test
  - Stage 2 embeddings (train/val/test .npy)
  - True labels

Trains a small MLP: [stage1_prob, gnn_emb_256] → logit
Evaluates against Stage 1 alone, Stage 2 alone.

Usage:
    python scripts/train_fusion.py
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

from chimera_fd.config import load_config
from chimera_fd.data.loader import load_parquet
from chimera_fd.evaluation.metrics import evaluate, find_best_threshold
from chimera_fd.features.engineering import get_feature_columns
from chimera_fd.models.fusion_head import FusionConfig, FusionTrainer
from chimera_fd.models.stage1_lightgbm import Stage1LightGBM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_fusion")


def main():
    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "ieee_cis"
    models_dir = ROOT / "models"
    reports_dir = ROOT / "reports"

    t0 = time.time()

    # ------ Load Stage 1 predictions on train/val/test ------
    log.info("Loading Stage 1 model + scoring all splits...")
    stage1 = Stage1LightGBM.load(models_dir / "stage1_lightgbm.pkl")

    train_df = load_parquet(processed / "train_features.parquet")
    val_df = load_parquet(processed / "val_features.parquet")
    test_df = load_parquet(processed / "test_features.parquet")

    feat_cols = get_feature_columns(train_df)

    train_s1 = stage1.predict_proba(train_df[feat_cols])
    val_s1 = stage1.predict_proba(val_df[feat_cols])
    test_s1 = stage1.predict_proba(test_df[feat_cols])

    log.info("Stage 1 scores: train=%s, val=%s, test=%s",
             train_s1.shape, val_s1.shape, test_s1.shape)

    # ------ Load Stage 2 embeddings ------
    log.info("Loading Stage 2 embeddings...")
    train_emb = np.load(models_dir / "stage2_train_emb.npy")
    val_emb = np.load(models_dir / "stage2_val_emb.npy")
    test_emb = np.load(models_dir / "stage2_test_emb.npy")
    log.info("Stage 2 embeddings: train=%s, val=%s, test=%s",
             train_emb.shape, val_emb.shape, test_emb.shape)

    # ------ Labels ------
    y_train = train_df["isFraud"].values
    y_val = val_df["isFraud"].values
    y_test = test_df["isFraud"].values

    # ------ pos_weight (same principle: no SMOTE) ------
    n_pos = int((y_train == 1).sum())
    n_neg = int((y_train == 0).sum())
    pos_weight = n_neg / max(n_pos, 1)
    log.info("pos_weight = %.2f", pos_weight)

    # ------ Baselines (for comparison) ------
    log.info("=" * 60)
    log.info("BASELINE — Stage 1 alone on TEST:")
    log.info("=" * 60)
    s1_test_report = evaluate(y_test, test_s1)
    log.info("  PR-AUC = %.4f  |  ROC-AUC = %.4f",
             s1_test_report.pr_auc, s1_test_report.roc_auc)

    # ------ Train Fusion Head ------
    log.info("=" * 60)
    log.info("Training Fusion Head")
    log.info("=" * 60)
    # v2: heavy regularization to prevent overfitting. v1 (hidden=128, dropout=0.3,
    # wd=1e-5) collapsed train loss but val PR-AUC stagnated.
    fusion_cfg = FusionConfig(
        hidden_dim=32,           # was 128 — tiny network, tiny capacity
        dropout=0.5,             # was 0.3 — hard regularization
        learning_rate=5e-4,      # was 1e-3 — slower learning
        weight_decay=1e-3,       # was 1e-5 — 100x stronger L2
        epochs=40,
        early_stopping_patience=8,
        batch_size=2048,
    )
    fusion = FusionTrainer(cfg=fusion_cfg)
    fusion.fit(
        train_stage1=train_s1, train_gnn_emb=train_emb, train_y=y_train,
        val_stage1=val_s1, val_gnn_emb=val_emb, val_y=y_val,
        pos_weight=pos_weight,
    )

    # ------ Evaluate Fusion ------
    log.info("=" * 60)
    log.info("Evaluating Fusion Head")
    log.info("=" * 60)
    val_fusion = fusion.predict_proba(val_s1, val_emb)
    test_fusion = fusion.predict_proba(test_s1, test_emb)

    val_report = evaluate(y_val, val_fusion)
    log.info("VAL metrics:\n%s", val_report.summary())

    best_thresh = find_best_threshold(y_val, val_fusion)
    test_report = evaluate(y_test, test_fusion, threshold=best_thresh)
    log.info("TEST metrics:\n%s", test_report.summary())

    # ------ Save ------
    fusion.save(models_dir / "fusion_head.pt")
    np.save(models_dir / "fusion_val_scores.npy", val_fusion)
    np.save(models_dir / "fusion_test_scores.npy", test_fusion)

    with open(reports_dir / "fusion_evaluation.json", "w") as f:
        json.dump({
            "val": val_report.as_dict(),
            "test": test_report.as_dict(),
            "chosen_threshold_from_val": best_thresh,
            "training_time_seconds": round(time.time() - t0, 1),
            "best_val_pr_auc_during_training": fusion.best_val_ap,
            "stage1_test_pr_auc": s1_test_report.pr_auc,
        }, f, indent=2)

    # ------ Headline comparison ------
    log.info("=" * 60)
    log.info("FUSION HEAD COMPLETE — %.1f seconds", time.time() - t0)
    log.info("=" * 60)
    log.info("COMPARISON:")
    log.info("  Stage 1 alone      : TEST PR-AUC = %.4f", s1_test_report.pr_auc)
    log.info("  Stage 2 alone      : TEST PR-AUC ~ 0.4336 (from stage2_evaluation.json)")
    log.info("  Fusion (LGBM+GNN) : TEST PR-AUC = %.4f", test_report.pr_auc)
    delta = test_report.pr_auc - s1_test_report.pr_auc
    log.info("  Fusion vs Stage 1  : %+.4f  (%+.1f%% relative)",
             delta, 100 * delta / s1_test_report.pr_auc)


if __name__ == "__main__":
    main()
