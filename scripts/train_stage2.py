"""Train the Stage 2 GraphSAGE specialist.

Loads engineered train/val/test -> picks top-K numeric features from Stage 1
importance -> fits scaler on train -> builds card1-sibling graphs -> trains
GraphSAGE with weighted BCE -> evaluates + saves model + embeddings.

Usage:
    python scripts/train_stage2.py
"""
from __future__ import annotations

import json
import logging
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from chimera_fd.config import load_config
from chimera_fd.data.loader import load_parquet
from chimera_fd.evaluation.metrics import evaluate, find_best_threshold
from chimera_fd.features.graph_builder import (
    build_transaction_graph,
    pick_top_k_features,
)
from chimera_fd.models.stage2_graphsage import GraphSAGEConfig, Stage2GraphSAGE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_stage2")


TOP_K_FEATURES = 150   # was 60 - more features = more signal
K_NEIGHBORS = 5


def main():
    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "ieee_cis"
    models_dir = ROOT / "models"
    reports_dir = ROOT / "reports"
    models_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    t0 = time.time()

    log.info("Loading engineered splits...")
    train_df = load_parquet(processed / "train_features.parquet")
    val_df = load_parquet(processed / "val_features.parquet")
    test_df = load_parquet(processed / "test_features.parquet")

    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        assert df["TransactionDT"].is_monotonic_increasing, f"{name} not sorted"

    imp_csv = reports_dir / "stage1_feature_importance.csv"
    top_feats = pick_top_k_features(imp_csv, k=TOP_K_FEATURES)
    log.info("Top %d features (first 10): %s", TOP_K_FEATURES, top_feats[:10])

    required_cols = set(top_feats) | {"card1", "TransactionDT", "isFraud"}
    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        missing = required_cols - set(df.columns)
        if missing:
            raise RuntimeError(f"{name} missing columns: {missing}")

    # ------ Fit scaler on train only ------
    log.info("Fitting StandardScaler on train features (NN training stability)...")
    scaler = StandardScaler()
    scaler.fit(train_df[top_feats].fillna(0).astype("float32").values)

    # ------ Build graphs with standardization ------
    log.info("=" * 60)
    log.info("Building graphs (k_neighbors=%d, standardized features)...", K_NEIGHBORS)
    log.info("=" * 60)
    train_g = build_transaction_graph(train_df, top_feats, k_neighbors=K_NEIGHBORS, scaler=scaler)
    val_g = build_transaction_graph(val_df, top_feats, k_neighbors=K_NEIGHBORS, scaler=scaler)
    test_g = build_transaction_graph(test_df, top_feats, k_neighbors=K_NEIGHBORS, scaler=scaler)

    with open(models_dir / "stage2_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    y_train = train_df["isFraud"].values
    n_pos = int((y_train == 1).sum())
    n_neg = int((y_train == 0).sum())
    pos_weight = n_neg / max(n_pos, 1)
    log.info("pos_weight = %.2f (n_neg=%d, n_pos=%d)", pos_weight, n_neg, n_pos)

    log.info("=" * 60)
    log.info("Training Stage 2 GraphSAGE")
    log.info("=" * 60)
    gs_cfg = GraphSAGEConfig(
        hidden_dim=256,
        num_layers=2,
        dropout=0.3,
        learning_rate=3e-3,
        weight_decay=1e-5,
        epochs=40,
        early_stopping_patience=7,
        batch_size=4096,
        num_neighbors=(30, 20),
    )
    trainer = Stage2GraphSAGE(cfg=gs_cfg)
    trainer.fit(train_g, val_g, feature_names=top_feats, pos_weight=pos_weight)

    log.info("=" * 60)
    log.info("Evaluating Stage 2 on val + test")
    log.info("=" * 60)
    val_scores = trainer.predict_proba(val_g)
    test_scores = trainer.predict_proba(test_g)

    val_report = evaluate(val_df["isFraud"].values, val_scores)
    log.info("VAL metrics:\n%s", val_report.summary())

    best_thresh = find_best_threshold(val_df["isFraud"].values, val_scores)
    test_report = evaluate(test_df["isFraud"].values, test_scores, threshold=best_thresh)
    log.info("TEST metrics:\n%s", test_report.summary())

    trainer.save(models_dir / "stage2_graphsage.pt")

    log.info("Extracting node embeddings for Fusion Head...")
    train_emb = trainer.get_embeddings(train_g)
    val_emb = trainer.get_embeddings(val_g)
    test_emb = trainer.get_embeddings(test_g)
    np.save(models_dir / "stage2_train_emb.npy", train_emb)
    np.save(models_dir / "stage2_val_emb.npy", val_emb)
    np.save(models_dir / "stage2_test_emb.npy", test_emb)
    log.info("Embeddings saved: train=%s, val=%s, test=%s",
             train_emb.shape, val_emb.shape, test_emb.shape)

    with open(reports_dir / "stage2_evaluation.json", "w") as f:
        json.dump({
            "val": val_report.as_dict(),
            "test": test_report.as_dict(),
            "chosen_threshold_from_val": best_thresh,
            "training_time_seconds": round(time.time() - t0, 1),
            "n_features_used": len(top_feats),
            "k_neighbors": K_NEIGHBORS,
            "hidden_dim": gs_cfg.hidden_dim,
            "learning_rate": gs_cfg.learning_rate,
            "best_val_pr_auc_during_training": trainer.best_val_ap,
            "features_used": top_feats,
        }, f, indent=2)

    log.info("=" * 60)
    log.info("STAGE 2 TRAINING COMPLETE - %.1f seconds", time.time() - t0)
    log.info("=" * 60)
    log.info("HEADLINE NUMBERS:")
    log.info("  VAL  PR-AUC = %.4f  |  ROC-AUC = %.4f", val_report.pr_auc, val_report.roc_auc)
    log.info("  TEST PR-AUC = %.4f  |  ROC-AUC = %.4f", test_report.pr_auc, test_report.roc_auc)


if __name__ == "__main__":
    main()
