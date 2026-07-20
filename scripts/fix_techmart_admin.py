"""Diagnostic + repair for TechMart admin login.

The BigBasket + TechMart backfill (seed_missing_companies.py) skipped TechMart
because a matching row already existed. This script figures out WHAT exists
(company row? admin user? both? with what values?) and repairs whichever
piece is broken so that admin@techmart.demo / TechMart@2026 login works.

Repair logic:
  - If company "TechMart Electronics" (or any variant) exists:
      * Ensure exactly one admin user with email=admin@techmart.demo linked to it
      * If that user exists -> reset password to TechMart@2026, ensure role=admin, active
      * If not -> create it fresh
  - If company DOES NOT exist:
      * Create it, then create the admin user

Idempotent: safe to run multiple times.

Usage:
    $env:DATABASE_URL = 'postgresql://user:pass@host/db'
    python scripts/fix_techmart_admin.py

Add --dry-run to see what it WOULD do without writing:
    python scripts/fix_techmart_admin.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import or_

from api.db.models import Company, User
from api.db.session import SessionLocal
from api.security import hash_password

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fix-techmart")


TARGET_COMPANY_NAME = "TechMart Electronics"
TARGET_EMAIL = "admin@techmart.demo"
TARGET_PASSWORD = "TechMart@2026"
TARGET_FULL_NAME = "TechMart Admin"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Print diagnosis only, do not write anything.")
    args = ap.parse_args()

    if not os.environ.get("DATABASE_URL"):
        log.error("DATABASE_URL is not set. Set it and retry.")
        sys.exit(1)

    log.info("=" * 60)
    log.info("TechMart admin repair — dry_run=%s", args.dry_run)
    log.info("Target DB: %s", os.environ["DATABASE_URL"].split("@")[-1])
    log.info("=" * 60)

    db = SessionLocal()
    try:
        # --- 1. Diagnose ------------------------------------------------
        # Find any TechMart-ish company (case-insensitive LIKE)
        companies = db.query(Company).filter(
            or_(
                Company.name.ilike("%techmart%"),
                Company.name.ilike("%tech mart%"),
                Company.name.ilike("%tech-mart%"),
            )
        ).all()

        # Find any user with the target email
        users_with_email = db.query(User).filter(User.email == TARGET_EMAIL).all()

        log.info("Found %d matching company row(s):", len(companies))
        for c in companies:
            log.info("  company_id=%s  name='%s'  industry='%s'  active=%s",
                     c.id, c.name, c.industry, c.is_active)

        log.info("Found %d user(s) with email=%s:", len(users_with_email), TARGET_EMAIL)
        for u in users_with_email:
            log.info("  user_id=%s  role=%s  active=%s  company_id=%s  full_name='%s'",
                     u.id, u.role, u.is_active, u.company_id, u.full_name)

        # --- 2. Decide target company ----------------------------------
        target_company: Company | None = None
        if len(companies) == 0:
            log.info("No TechMart company found — will create fresh.")
        elif len(companies) == 1:
            target_company = companies[0]
            log.info("Will use existing company_id=%s", target_company.id)
        else:
            # multiple matches — pick exact-name match, else first
            exact = [c for c in companies if c.name == TARGET_COMPANY_NAME]
            target_company = exact[0] if exact else companies[0]
            log.warning(
                "Multiple TechMart-ish rows exist — using company_id=%s (name='%s'). "
                "Other rows left alone; inspect manually if needed.",
                target_company.id, target_company.name,
            )

        if args.dry_run:
            log.info("DRY RUN — no writes.")
            log.info("Plan:")
            if target_company is None:
                log.info("  1. CREATE Company '%s'", TARGET_COMPANY_NAME)
                log.info("  2. CREATE User email=%s role=admin", TARGET_EMAIL)
            else:
                existing_admin = next((u for u in users_with_email
                                       if u.company_id == target_company.id), None)
                if existing_admin:
                    log.info("  1. RESET password + ensure role=admin + is_active=True on user_id=%s",
                             existing_admin.id)
                else:
                    log.info("  1. CREATE User email=%s role=admin linked to company_id=%s",
                             TARGET_EMAIL, target_company.id)
                # Warn about orphan users
                orphans = [u for u in users_with_email if u.company_id != target_company.id]
                if orphans:
                    for u in orphans:
                        log.warning("  ORPHAN user_id=%s belongs to company_id=%s (not target). Manual inspection.",
                                    u.id, u.company_id)
            return

        # --- 3. Repair --------------------------------------------------
        if target_company is None:
            target_company = Company(
                name=TARGET_COMPANY_NAME,
                industry="E-commerce (Electronics)",
                size="SMB (51-500)",
                use_case="USD-denominated demo storefront — used by CHIMERA-FD's public /checkout page.",
                logo_url=None,
                is_active=True,
            )
            db.add(target_company)
            db.flush()
            log.info("CREATED company_id=%s '%s'", target_company.id, target_company.name)

        # Find admin user linked to target company
        existing_admin = next((u for u in users_with_email
                               if u.company_id == target_company.id), None)

        if existing_admin:
            existing_admin.hashed_password = hash_password(TARGET_PASSWORD)
            existing_admin.role = "admin"
            existing_admin.is_active = True
            if not existing_admin.full_name:
                existing_admin.full_name = TARGET_FULL_NAME
            log.info("RESET user_id=%s (password + role=admin + active=True)", existing_admin.id)
        else:
            # If email exists but linked to WRONG company -> we skip modification
            # to avoid stealing an email. User must resolve manually.
            wrong_company_users = [u for u in users_with_email
                                   if u.company_id != target_company.id]
            if wrong_company_users:
                for u in wrong_company_users:
                    log.error(
                        "CONFLICT — user_id=%s has email=%s but is linked to company_id=%s "
                        "(not target company_id=%s). Refusing to modify. Delete or reassign manually.",
                        u.id, u.email, u.company_id, target_company.id,
                    )
                db.rollback()
                sys.exit(2)

            # Safe to create fresh admin
            admin = User(
                email=TARGET_EMAIL,
                hashed_password=hash_password(TARGET_PASSWORD),
                full_name=TARGET_FULL_NAME,
                role="admin",
                is_active=True,
                company_id=target_company.id,
            )
            db.add(admin)
            db.flush()
            log.info("CREATED user_id=%s email=%s role=admin", admin.id, admin.email)

        db.commit()
        log.info("=" * 60)
        log.info("DONE — login should now work:")
        log.info("  Email:    %s", TARGET_EMAIL)
        log.info("  Password: %s", TARGET_PASSWORD)
        log.info("=" * 60)

    except SystemExit:
        raise
    except Exception:
        db.rollback()
        log.exception("Repair failed — transaction rolled back.")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
