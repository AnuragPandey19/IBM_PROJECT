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
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--use-augmented", action="store_true",
                    help="Load train_features.parquet + train_augmented.parquet "
                         "(the extra rows produced by augment_sparkov_training.py) "
                         "instead of re-engineering features from raw CSVs. "
                         "Val + test parquet still come from the previous run.")
    args = ap.parse_args()

    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "sparkov"
    processed.mkdir(parents=True, exist_ok=True)
    models_dir = ROOT / "models"
    reports_dir = ROOT / "reports"

    t0 = time.time()

    # ------ Load path split: augmented reuse vs fresh raw ------
    if args.use_augmented:
        # AUGMENTED PATH: skip raw-CSV load + feature engineering, reuse
        # the parquet files already on disk from a previous run + the new
        # synthetic rows produced by augment_sparkov_training.py.
        train_ft_path = processed / "train_features.parquet"
        val_ft_path   = processed / "val_features.parquet"
        test_ft_path  = processed / "test_features.parquet"
        aug_path      = processed / "train_augmented.parquet"

        missing = [p for p in (train_ft_path, val_ft_path, test_ft_path)
                   if not p.exists()]
        if missing:
            raise SystemExit(
                "--use-augmented requires engineered parquet files from a "
                f"previous train_sparkov.py run. Missing: {missing}. "
                "Run once without --use-augmented first, then re-run with the flag."
            )

        log.info("AUGMENTED path: loading engineered parquets from %s", processed)
        train_ft = pd.read_parquet(train_ft_path)
        val_ft   = pd.read_parquet(val_ft_path)
        test_ft  = pd.read_parquet(test_ft_path)

        if aug_path.exists():
            aug_ft = pd.read_parquet(aug_path)
            log.info("Loaded augmentation rows: +%d (fraud rate %.3f%%)",
                     len(aug_ft), 100 * aug_ft["is_fraud"].mean())
            # Filter augmented rows to only columns that exist in train_ft
            # (defensive — augment script preserves donor columns but ensures
            # every training column is present).
            missing_cols = set(train_ft.columns) - set(aug_ft.columns)
            if missing_cols:
                log.warning("Augmented rows missing cols %s — filling zeros",
                            missing_cols)
                for c in missing_cols:
                    aug_ft[c] = 0
            aug_ft = aug_ft[train_ft.columns]
            train_ft = pd.concat([train_ft, aug_ft], axis=0, ignore_index=True)
            # Reshuffle so augmented rows aren't all at the bottom
            train_ft = train_ft.sample(frac=1.0, random_state=42).reset_index(drop=True)
        else:
            log.warning("--use-augmented set but train_augmented.parquet not found. "
                        "Training on original engineered parquet only. Run "
                        "scripts/augment_sparkov_training.py first.")

        log.info("Final train shape: %d rows, fraud rate %.3f%%",
                 len(train_ft), 100 * train_ft["is_fraud"].mean())
    else:
        # FRESH PATH: original behavior — raw CSVs + feature engineering.
        log.info("Loading Sparkov raw CSVs...")
        train_raw, test_raw = load_sparkov(
            cfg.data.sparkov.train,
            cfg.data.sparkov.test,
        )
        merged = pd.concat([train_raw, test_raw], axis=0, ignore_index=True)
        log.info("Merged Sparkov: %d rows. Fraud rate: %.3f%%",
                 len(merged), 100 * merged["is_fraud"].mean())

        train_df, val_df, test_df = time_based_split(
            merged, time_col="unix_time",
            train_frac=0.80, val_frac=0.10, test_frac=0.10,
        )

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

    # ------ Per-typology stress evaluation (V4 audit T-4 + T-6 + B-6) ---
    # Every retrain should quantify per-typology recall so retrain deltas
    # can be measured. This uses the same 12 typologies that V1/V2/V3
    # tested against, on the labeled test cases file produced by our
    # teammates. If the file isn't present, the stress-eval block is
    # skipped with a warning rather than failing the retrain.
    typology_report: dict | None = None
    try:
        typology_report = _run_typology_stress_eval(trainer, feat_cols, ROOT, log)
    except Exception as e:
        log.warning("per-typology stress eval skipped: %s", e)

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
            # Per-typology stress evaluation (audit T-4 + T-6 + B-6).
            # Compare across retrains to detect regressions on the four
            # blind spots we know about (card_testing, velocity_spike,
            # cross_category_fraud, late_night_hostel).
            "typology_stress": typology_report,
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


def _run_typology_stress_eval(trainer, feat_cols: list[str], root: Path, log) -> dict | None:
    """Score the freshly-trained model on a labeled per-typology test set
    and produce a per-typology recall + PR-AUC breakdown.

    Reads from `evaluation/test_cases/test_cases_v1_by_pankaj.labeled.jsonl`
    (150K rows) if present. Falls back to the smaller Gurnoor v1/v2 files.
    Returns None if none of the labeled files exist. Also checks the repo
    root as a legacy fallback (older layout before the evaluation/ reorg).

    Output shape:
        {
          "source_file": "evaluation/test_cases/test_cases_v1_by_pankaj.labeled.jsonl",
          "total_rows": 150000,
          "per_typology": {
            "card_testing":   {"total": 11715, "positive_predictions": ..., "recall": ...},
            ...
          }
        }
    """
    import json as _json

    # Search order: prefer largest, most-recently-authored labeled set.
    # New home is evaluation/test_cases/; keep root fallbacks for backward
    # compatibility with older checkouts (delete once everyone's on new layout).
    tc_dir = root / "evaluation" / "test_cases"
    candidates = [
        tc_dir / "test_cases_v1_by_pankaj.labeled.jsonl",
        tc_dir / "test_cases_v2_by_gurnoor.CLEAN.dedup.jsonl",
        tc_dir / "test cases_v1_by_Gurnoor.labeled.jsonl",
        # legacy root-level locations (pre-reorg)
        root / "test_cases_v1_by_pankaj.labeled.jsonl",
        root / "test_cases_v2_by_gurnoor.CLEAN.dedup.jsonl",
        root / "test cases_v1_by_Gurnoor.labeled.jsonl",
    ]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        log.warning("No labeled test-cases file found for typology stress eval. "
                    "Skipping. Files searched: %s", [str(p) for p in candidates])
        return None

    log.info("Typology stress eval reading: %s", src)
    rows = []
    with src.open() as f:
        for line in f:
            if not line.strip():
                continue
            r = _json.loads(line)
            rows.append(r)
    log.info("Loaded %d labeled rows across %d typologies", len(rows),
             len({r.get("typology") for r in rows}))

    # For efficiency at 150K scale, sample down to at most 3000 per typology.
    from collections import defaultdict
    by_typo: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        t = r.get("typology")
        if t:
            by_typo[t].append(r)

    import random as _r
    _r.seed(42)
    sampled: list[dict] = []
    for typo, subset in by_typo.items():
        _r.shuffle(subset)
        sampled.extend(subset[:3000])
    log.info("Stress evaluating on %d sampled rows (max 3000/typology)",
             len(sampled))

    # For each row, build features using the SAME enrichment logic /
    # api/checkout uses, then score. Skip rows the feature builder can't
    # process (invalid payload, missing profile, etc.) rather than crash.
    sys.path.insert(0, str(root))
    from api.routes.checkout import _build_sparkov_row, CUSTOMER_PROFILES  # noqa
    from api.schemas.checkout import CheckoutRequest  # noqa
    from datetime import datetime, timezone

    per_typo: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "positive_predictions": 0, "review_predictions": 0,
                 "block_predictions": 0, "correct_fraud": 0, "correct_legit": 0}
    )

    now = datetime.now(timezone.utc)
    day_of_week = now.weekday()

    approve_below = 0.010  # matches _SPARKOV_APPROVE_BELOW
    block_above = 0.05     # matches _SPARKOV_BLOCK_ABOVE

    for r in sampled:
        typo = r["typology"]
        label = r["label"]
        pl = r.get("payload", {})
        try:
            req = CheckoutRequest(**{
                k: v for k, v in pl.items() if k in {
                    "card_number", "cardholder_name", "amount", "merchant_name",
                    "merchant_category", "cust_email", "demo_profile",
                    "demo_hour_override",
                }
            })
            profile = CUSTOMER_PROFILES.get(pl.get("demo_profile"), CUSTOMER_PROFILES["new"])
            hour = pl.get("demo_hour_override", now.hour)
            X = _build_sparkov_row(req, profile, hour, day_of_week)
            X_use = X[trainer.feature_names]
        except Exception:
            continue

        # Direct model prediction (skip augmenter — we're measuring the model)
        score = float(trainer.predict_proba(X_use)[0])
        if score < approve_below:
            pred = "approve"
        elif score > block_above:
            pred = "block"
        else:
            pred = "review"

        b = per_typo[typo]
        b["total"] += 1
        if pred == "block":
            b["block_predictions"] += 1
            if label == "fraud":
                b["correct_fraud"] += 1
        elif pred == "approve":
            b["positive_predictions"] += 1
            if label == "legit":
                b["correct_legit"] += 1
        else:
            b["review_predictions"] += 1

    # Convert to human-readable structure
    typology_summary = {}
    for t, b in per_typo.items():
        tot = b["total"]
        # For fraud typologies: recall = block / total. For legit: approve / total.
        typology_summary[t] = {
            **b,
            "block_rate": round(b["block_predictions"] / tot, 4) if tot else 0.0,
            "approve_rate": round(b["positive_predictions"] / tot, 4) if tot else 0.0,
            "review_rate": round(b["review_predictions"] / tot, 4) if tot else 0.0,
        }
        log.info("  %-26s n=%5d  block=%.1f%%  approve=%.1f%%  review=%.1f%%",
                 t, tot,
                 typology_summary[t]["block_rate"] * 100,
                 typology_summary[t]["approve_rate"] * 100,
                 typology_summary[t]["review_rate"] * 100)

    return {
        "source_file": str(src.name),
        "total_rows_sampled": len(sampled),
        "per_typology": typology_summary,
    }


if __name__ == "__main__":
    main()
