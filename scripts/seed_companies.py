"""Seed 5 sample companies with admin users and demo transactions.

This is a destructive migration script — it drops and re-creates all tables
to accommodate the new multi-tenant schema, then populates:

  - 5 sample companies (Razorpay, Zomato, Swiggy, HDFC Bank, ICICI Bank)
  - 1 admin analyst per company with predetermined credentials
  - ~10 scored transactions per company (varied fraud/legit mix)

Usage (from local machine with DATABASE_URL pointing to Render Postgres):

    # PowerShell
    $env:DATABASE_URL = "postgresql://user:pass@host.render.com/db"
    python scripts/seed_companies.py --reset

The --reset flag is REQUIRED for the migration (drops all tables). Any new
company signing up post-seed will get an empty dashboard as expected.
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

from api.db.base import Base
from api.db.models import Company, Prediction, Transaction, User
from api.db.session import SessionLocal, engine
from api.security import hash_password
from api.services.model_service import get_model_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")


# ==========================================================================
# Sample companies + credentials
# ==========================================================================
SAMPLE_COMPANIES = [
    {
        "name": "Razorpay",
        "industry": "Payment Gateway",
        "size": "Enterprise",
        "use_case": "Merchant fraud screening for 5M+ Indian businesses accepting online payments.",
        "logo_url": None,
        "admin_email": "admin@razorpay.demo",
        "admin_password": "Razorpay@2026",
        "admin_name": "Razorpay Admin",
    },
    {
        "name": "Zomato",
        "industry": "E-commerce (Food Delivery)",
        "size": "Enterprise",
        "use_case": "Detecting synthetic accounts and refund abuse across 300K restaurants.",
        "logo_url": None,
        "admin_email": "admin@zomato.demo",
        "admin_password": "Zomato@2026",
        "admin_name": "Zomato Admin",
    },
    {
        "name": "Swiggy",
        "industry": "E-commerce (Food Delivery)",
        "size": "Enterprise",
        "use_case": "Preventing chargeback fraud on card-not-present food orders.",
        "logo_url": None,
        "admin_email": "admin@swiggy.demo",
        "admin_password": "Swiggy@2026",
        "admin_name": "Swiggy Admin",
    },
    {
        "name": "HDFC Bank",
        "industry": "Banking",
        "size": "Enterprise",
        "use_case": "Real-time fraud scoring for retail card transactions.",
        "logo_url": None,
        "admin_email": "admin@hdfcbank.demo",
        "admin_password": "HDFC@2026",
        "admin_name": "HDFC Bank Admin",
    },
    {
        "name": "ICICI Bank",
        "industry": "Banking",
        "size": "Enterprise",
        "use_case": "Cross-border transaction monitoring and account takeover detection.",
        "logo_url": None,
        "admin_email": "admin@icicibank.demo",
        "admin_password": "ICICI@2026",
        "admin_name": "ICICI Bank Admin",
    },
]

TXNS_PER_COMPANY = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", required=True,
                    help="Drop all tables and recreate (required for multi-tenant migration)")
    ap.add_argument("--source", default="data/processed/ieee_cis/samples.parquet",
                    help="Parquet file for demo transactions")
    args = ap.parse_args()

    if not args.reset:
        log.error("Must pass --reset to run this migration script.")
        sys.exit(1)

    parquet_path = ROOT / args.source
    if not parquet_path.exists():
        # Fallback to full test features parquet
        parquet_path = ROOT / "data" / "processed" / "ieee_cis" / "test_features.parquet"
        if not parquet_path.exists():
            log.error("Neither samples.parquet nor test_features.parquet found.")
            sys.exit(1)

    log.info("=" * 60)
    log.info("CHIMERA-FD Multi-Tenant Seed")
    log.info("=" * 60)

    # -----------------------------------------------------------------------
    # 1. Drop + recreate schema
    # -----------------------------------------------------------------------
    log.info("Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)
    log.info("Creating fresh tables with multi-tenant schema...")
    Base.metadata.create_all(bind=engine)

    # -----------------------------------------------------------------------
    # 2. Load model + parquet
    # -----------------------------------------------------------------------
    log.info("Loading model service...")
    ms = get_model_service()
    ms.load()

    log.info("Loading demo parquet from %s ...", parquet_path)
    df = pd.read_parquet(parquet_path)
    log.info("Loaded %d rows, %d columns", len(df), df.shape[1])

    # Sample enough rows for all 5 companies (with variety)
    total_needed = len(SAMPLE_COMPANIES) * TXNS_PER_COMPANY
    fraud_rows = df[df.get("isFraud", 0) == 1]
    legit_rows = df[df.get("isFraud", 0) == 0]

    # 3 fraud + 7 legit per company for a ~30% fraud rate that looks realistic
    fraud_per_co = 3
    legit_per_co = 7

    n_fraud_needed = fraud_per_co * len(SAMPLE_COMPANIES)
    n_legit_needed = legit_per_co * len(SAMPLE_COMPANIES)

    fraud_sample = fraud_rows.sample(n=min(n_fraud_needed, len(fraud_rows)), random_state=42)
    legit_sample = legit_rows.sample(n=min(n_legit_needed, len(legit_rows)), random_state=42)

    log.info("Selected %d fraud + %d legit rows for demo",
             len(fraud_sample), len(legit_sample))

    # -----------------------------------------------------------------------
    # 3. Create companies + admin users + transactions
    # -----------------------------------------------------------------------
    db = SessionLocal()
    try:
        credentials_log = []

        for co_idx, co_data in enumerate(SAMPLE_COMPANIES):
            # Create company
            company = Company(
                name=co_data["name"],
                industry=co_data["industry"],
                size=co_data["size"],
                use_case=co_data["use_case"],
                logo_url=co_data["logo_url"],
                is_active=True,
            )
            db.add(company)
            db.flush()  # get company.id

            # Create admin user
            admin = User(
                email=co_data["admin_email"],
                hashed_password=hash_password(co_data["admin_password"]),
                full_name=co_data["admin_name"],
                role="admin",
                is_active=True,
                company_id=company.id,
            )
            db.add(admin)
            db.flush()

            # Pick 3 fraud + 7 legit rows for this company
            co_fraud = fraud_sample.iloc[co_idx * fraud_per_co : (co_idx + 1) * fraud_per_co]
            co_legit = legit_sample.iloc[co_idx * legit_per_co : (co_idx + 1) * legit_per_co]
            co_rows = pd.concat([co_fraud, co_legit]).reset_index(drop=True)

            # Batch score
            X = co_rows[ms.feature_columns].copy()
            result = ms.score(X)
            shap_lists = ms.shap(X, top_k=5)

            # Insert transactions + predictions
            for i in range(len(co_rows)):
                row = co_rows.iloc[i]
                ext = f"seed-{co_data['name'].lower().replace(' ', '')}-{int(row['TransactionID'])}"

                raw = {}
                for c in ["TransactionID", "TransactionDT", "TransactionAmt", "isFraud",
                          "ProductCD", "card1", "card4", "card6", "addr1",
                          "P_emaildomain", "DeviceType", "DeviceInfo"]:
                    if c in co_rows.columns:
                        v = row[c]
                        if pd.notna(v):
                            raw[c] = v.item() if hasattr(v, "item") else v

                txn = Transaction(
                    external_id=ext,
                    transaction_dt=int(row["TransactionDT"]) if "TransactionDT" in co_rows.columns else None,
                    amount=float(row["TransactionAmt"]),
                    card1=str(int(row["card1"])) if "card1" in co_rows.columns and pd.notna(row["card1"]) else None,
                    card4=str(row["card4"]) if "card4" in co_rows.columns and pd.notna(row["card4"]) else None,
                    card6=str(row["card6"]) if "card6" in co_rows.columns and pd.notna(row["card6"]) else None,
                    product_cd=str(row["ProductCD"]) if "ProductCD" in co_rows.columns and pd.notna(row["ProductCD"]) else None,
                    addr1=str(int(row["addr1"])) if "addr1" in co_rows.columns and pd.notna(row["addr1"]) else None,
                    p_emaildomain=str(row["P_emaildomain"]) if "P_emaildomain" in co_rows.columns and pd.notna(row["P_emaildomain"]) else None,
                    device_type=str(row["DeviceType"]) if "DeviceType" in co_rows.columns and pd.notna(row["DeviceType"]) else None,
                    device_info=str(row["DeviceInfo"]) if "DeviceInfo" in co_rows.columns and pd.notna(row["DeviceInfo"]) else None,
                    raw_features=raw,
                    is_fraud=bool(row["isFraud"]) if "isFraud" in co_rows.columns else None,
                    company_id=company.id,
                )
                db.add(txn)
                db.flush()

                pred = Prediction(
                    transaction_id=txn.id,
                    raw_score=float(result["raw_scores"][i]),
                    calibrated_score=float(result["calibrated_scores"][i]),
                    decision=result["decisions"][i],
                    model_version=ms.model_version,
                    shap_top=shap_lists[i],
                    latency_ms=None,
                    company_id=company.id,
                )
                db.add(pred)

            log.info("Created %s: %d txns, admin=%s",
                     co_data["name"], len(co_rows), co_data["admin_email"])
            credentials_log.append((co_data["name"], co_data["admin_email"], co_data["admin_password"]))

        db.commit()

    finally:
        db.close()

    # -----------------------------------------------------------------------
    # 4. Print credentials summary
    # -----------------------------------------------------------------------
    log.info("=" * 60)
    log.info("SEED COMPLETE — DEMO CREDENTIALS")
    log.info("=" * 60)
    print()
    print(f"{'Company':<15} {'Email':<28} {'Password':<20}")
    print("-" * 65)
    for name, email, pw in credentials_log:
        print(f"{name:<15} {email:<28} {pw:<20}")
    print()
    log.info("Any NEW signup after this will create a fresh company with empty dashboard.")


if __name__ == "__main__":
    main()
