"""Incremental seed — adds BigBasket + TechMart Electronics without dropping any tables.

This is the safe, idempotent counterpart to seed_companies.py --reset.
Use this when the destructive reset script was run BEFORE these two companies
were added to SAMPLE_COMPANIES, and you now need to backfill them in production.

Behavior:
  - Connects using DATABASE_URL env var (must be set to production Postgres URL)
  - For each of the two missing companies:
      * If company row with same name already exists -> SKIP (idempotent)
      * Otherwise create Company + admin User with hashed password
  - Does NOT create demo transactions (keeps script lean; not strictly required
    for login demo). If you want demo transactions for these two, run the
    full seed_companies.py --reset (destructive) instead.

Usage (from repo root, .venv active):
    # PowerShell
    $env:DATABASE_URL = "postgresql://user:pass@dpg-xxx.render.com/dbname"
    python scripts/seed_missing_companies.py

    # bash / WSL
    export DATABASE_URL="postgresql://user:pass@dpg-xxx.render.com/dbname"
    python scripts/seed_missing_companies.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from api.db.models import Company, User
from api.db.session import SessionLocal
from api.security import hash_password

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed-missing")


MISSING_COMPANIES = [
    {
        "name": "BigBasket",
        "industry": "E-commerce (Groceries)",
        "size": "Enterprise",
        "use_case": "Screening online grocery orders and Instamart-style rapid delivery.",
        "logo_url": None,
        "admin_email": "admin@bigbasket.demo",
        "admin_password": "BigBasket@2026",
        "admin_name": "BigBasket Admin",
    },
    {
        "name": "TechMart Electronics",
        "industry": "E-commerce (Electronics)",
        "size": "SMB (51-500)",
        "use_case": "USD-denominated demo storefront — used by CHIMERA-FD's public /checkout page.",
        "logo_url": None,
        "admin_email": "admin@techmart.demo",
        "admin_password": "TechMart@2026",
        "admin_name": "TechMart Admin",
    },
]


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL env var is not set. Set it to your Render Postgres URL and retry.")
        sys.exit(1)

    log.info("=" * 60)
    log.info("Incremental seed — BigBasket + TechMart Electronics")
    log.info("Target DB: %s", os.environ["DATABASE_URL"].split("@")[-1])
    log.info("=" * 60)

    db = SessionLocal()
    created = []
    skipped = []
    try:
        for co in MISSING_COMPANIES:
            existing = db.query(Company).filter(Company.name == co["name"]).first()
            if existing:
                log.info("SKIP  %-22s already exists (company_id=%s)", co["name"], existing.id)
                skipped.append(co["name"])
                continue

            # Also check that the admin email isn't taken (defensive)
            existing_user = db.query(User).filter(User.email == co["admin_email"]).first()
            if existing_user:
                log.warning(
                    "SKIP  %-22s company row missing but admin email %s already exists (user_id=%s). "
                    "Manual cleanup needed.",
                    co["name"], co["admin_email"], existing_user.id,
                )
                skipped.append(co["name"])
                continue

            company = Company(
                name=co["name"],
                industry=co["industry"],
                size=co["size"],
                use_case=co["use_case"],
                logo_url=co["logo_url"],
                is_active=True,
            )
            db.add(company)
            db.flush()

            admin = User(
                email=co["admin_email"],
                hashed_password=hash_password(co["admin_password"]),
                full_name=co["admin_name"],
                role="admin",
                is_active=True,
                company_id=company.id,
            )
            db.add(admin)
            db.flush()

            log.info("ADD   %-22s company_id=%s admin=%s", co["name"], company.id, co["admin_email"])
            created.append((co["name"], co["admin_email"], co["admin_password"]))

        db.commit()

    except Exception:
        db.rollback()
        log.exception("Seed failed — transaction rolled back.")
        sys.exit(1)
    finally:
        db.close()

    log.info("=" * 60)
    log.info("DONE — %d created, %d skipped", len(created), len(skipped))
    log.info("=" * 60)

    if created:
        print()
        print(f"{'Company':<22} {'Email':<28} {'Password':<20}")
        print("-" * 72)
        for name, email, pw in created:
            print(f"{name:<22} {email:<28} {pw:<20}")
        print()
        log.info("Login should now work at the live URL for the above accounts.")

    if skipped:
        log.info(
            "Skipped %d already-present or conflicted companies: %s",
            len(skipped), ", ".join(skipped),
        )


if __name__ == "__main__":
    main()
