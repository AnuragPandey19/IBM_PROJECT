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


# IEEE-CIS LabelEncoder inverse mappings — training encoder sorted alphabetically
# and started at 1 (0 reserved for NaN when present). test_features.parquet stores
# encoded integers; the DB and dashboard need to show human-readable strings.
IEEE_PRODUCT_CD_REV = {1: "C", 2: "H", 3: "R", 4: "S", 5: "W"}
IEEE_CARD4_REV = {1: "amex", 2: "discover", 3: "mastercard", 4: "visa"}
IEEE_CARD6_REV = {1: "charge", 2: "credit", 3: "debit", 4: "debit or credit"}
IEEE_DEVICE_TYPE_REV = {1: "unknown", 2: "desktop", 3: "mobile"}


def _decode(raw, mapping):
    """Convert an encoded int (or int-like) value back to its string label.
    Passes strings through unchanged so already-decoded parquets still work.
    Returns None for NaN / empty."""
    if raw is None:
        return None
    try:
        if hasattr(raw, "item"):
            raw = raw.item()
        if isinstance(raw, str) and not raw.isdigit():
            return raw
        n = int(float(raw))
        return mapping.get(n)
    except (ValueError, TypeError):
        return str(raw)


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
                card4=_decode(row.get("card4") if "card4" in df.columns and pd.notna(row.get("card4")) else None, IEEE_CARD4_REV),
                card6=_decode(row.get("card6") if "card6" in df.columns and pd.notna(row.get("card6")) else None, IEEE_CARD6_REV),
                product_cd=_decode(row.get("ProductCD") if "ProductCD" in df.columns and pd.notna(row.get("ProductCD")) else None, IEEE_PRODUCT_CD_REV),
                addr1=str(int(row["addr1"])) if "addr1" in df.columns and pd.notna(row["addr1"]) else None,
                p_emaildomain=str(row["P_emaildomain"]) if "P_emaildomain" in df.columns and pd.notna(row["P_emaildomain"]) else None,
                device_type=_decode(row.get("DeviceType") if "DeviceType" in df.columns and pd.notna(row.get("DeviceType")) else None, IEEE_DEVICE_TYPE_REV),
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
