"""Bulk-load test.parquet transactions into the API database, WITH predictions.

For each row: build features, score with Stage 1 + Stage 3, save transaction +
prediction to DB. Dashboard then has real data to display.

Usage:
    python scripts/seed_transactions.py --limit 500
    python scripts/seed_transactions.py --limit 5000 --skip-shap  (faster)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from api.config import get_settings
from api.db.models import Prediction, Transaction
from api.db.session import SessionLocal, init_db
from api.services.model_service import get_model_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")


CORE_COLS = [
    "TransactionID", "TransactionDT", "TransactionAmt", "isFraud",
    "ProductCD", "card1", "card4", "card6", "addr1",
    "P_emaildomain", "DeviceType", "DeviceInfo",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/processed/ieee_cis/test_features.parquet",
                    help="Parquet file to seed from")
    ap.add_argument("--limit", type=int, default=500, help="Max rows to load")
    ap.add_argument("--reset", action="store_true",
                    help="Delete existing seed-* transactions before inserting")
    ap.add_argument("--skip-shap", action="store_true",
                    help="Don't compute SHAP for each row (5x faster)")
    args = ap.parse_args()

    settings = get_settings()
    parquet_path = ROOT / args.source
    if not parquet_path.exists():
        raise SystemExit(f"Missing parquet: {parquet_path}")

    log.info("Loading %s ...", parquet_path)
    df = pd.read_parquet(parquet_path)
    log.info("Loaded %d rows, %d columns", len(df), df.shape[1])

    if args.limit < len(df):
        df = df.sample(n=args.limit, random_state=42).reset_index(drop=True)
        log.info("Sampled %d rows", len(df))

    log.info("Loading model...")
    init_db()
    ms = get_model_service()
    ms.load()

    if args.reset:
        from sqlalchemy import delete
        db_reset = SessionLocal()
        try:
            existing = db_reset.query(Transaction).filter(
                Transaction.external_id.like("seed-%")
            ).all()
            log.info("Resetting: deleting %d existing seed transactions...", len(existing))
            for t in existing:
                db_reset.delete(t)
            db_reset.commit()
        finally:
            db_reset.close()

    log.info("Scoring %d rows in one batch...", len(df))
    t0 = time.time()
    X = df[ms.feature_columns].copy()
    result = ms.score(X)
    log.info("Batch scored in %.1f s (avg %.2f ms/row)",
             time.time() - t0,
             1000 * (time.time() - t0) / max(len(df), 1))

    if not args.skip_shap:
        log.info("Computing SHAP (top-5 per row)...")
        shap_lists = ms.shap(X, top_k=5)
    else:
        shap_lists = [None] * len(df)

    log.info("Inserting into DB...")
    db = SessionLocal()
    try:
        # Get existing external_ids to skip duplicates (when --reset not used)
        existing_ids = set()
        if not args.reset:
            rows = db.query(Transaction.external_id).filter(
                Transaction.external_id.like("seed-%")
            ).all()
            existing_ids = {r[0] for r in rows}
            if existing_ids:
                log.info("Skipping %d existing seed transactions", len(existing_ids))

        txn_objects = []
        pred_objects = []
        skip_indices = []
        for i in range(len(df)):
            row = df.iloc[i]
            ext = f"seed-{int(row['TransactionID'])}" if "TransactionID" in df.columns else None
            if ext and ext in existing_ids:
                skip_indices.append(i)
                continue
            raw = {}
            for c in CORE_COLS:
                if c in df.columns:
                    v = row[c]
                    if pd.notna(v):
                        raw[c] = v.item() if hasattr(v, "item") else v

            txn = Transaction(
                external_id=f"seed-{int(row['TransactionID'])}" if "TransactionID" in df.columns else None,
                transaction_dt=int(row["TransactionDT"]) if "TransactionDT" in df.columns else None,
                amount=float(row["TransactionAmt"]),
                card1=str(int(row["card1"])) if "card1" in df.columns and pd.notna(row["card1"]) else None,
                card4=str(row["card4"]) if "card4" in df.columns and pd.notna(row["card4"]) else None,
                card6=str(row["card6"]) if "card6" in df.columns and pd.notna(row["card6"]) else None,
                product_cd=str(row["ProductCD"]) if "ProductCD" in df.columns and pd.notna(row["ProductCD"]) else None,
                addr1=str(int(row["addr1"])) if "addr1" in df.columns and pd.notna(row["addr1"]) else None,
                p_emaildomain=str(row["P_emaildomain"]) if "P_emaildomain" in df.columns and pd.notna(row["P_emaildomain"]) else None,
                device_type=str(row["DeviceType"]) if "DeviceType" in df.columns and pd.notna(row["DeviceType"]) else None,
                device_info=str(row["DeviceInfo"]) if "DeviceInfo" in df.columns and pd.notna(row["DeviceInfo"]) else None,
                raw_features=raw,
                is_fraud=bool(row["isFraud"]) if "isFraud" in df.columns else None,
            )
            txn_objects.append(txn)

        db.add_all(txn_objects)
        db.flush()

        # Map txn_objects back to their original df indices for score lookup
        kept_indices = [i for i in range(len(df)) if i not in skip_indices]
        for k, txn in enumerate(txn_objects):
            orig_i = kept_indices[k]
            pred = Prediction(
                transaction_id=txn.id,
                raw_score=float(result["raw_scores"][orig_i]),
                calibrated_score=float(result["calibrated_scores"][orig_i]),
                decision=result["decisions"][orig_i],
                model_version=ms.model_version,
                shap_top=shap_lists[orig_i],
                latency_ms=None,
            )
            pred_objects.append(pred)

        db.add_all(pred_objects)
        db.commit()
        log.info("Inserted %d transactions + %d predictions",
                 len(txn_objects), len(pred_objects))
    finally:
        db.close()

    log.info("Done in %.1f s total.", time.time() - t0)


if __name__ == "__main__":
    main()
