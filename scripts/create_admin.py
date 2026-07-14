"""Bootstrap an admin user attached to a company.

Multi-tenant model: every user must have a company_id, else require_company()
rejects all their requests. This script either attaches the admin to an
existing company by name, or creates a new company on the fly.

Usage:
    # Create admin for existing company
    python scripts/create_admin.py --email admin@zomato.local \\
        --password strongpass123 --company-name Zomato

    # Create both company and admin in one go
    python scripts/create_admin.py --email admin@newco.local \\
        --password strongpass123 --company-name "NewCo Inc" \\
        --create-company --industry "E-commerce" --size "Startup (1-50)"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from api.db.models import Company, User
from api.db.session import SessionLocal, init_db
from api.security import hash_password


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--full-name", default="Admin User")
    ap.add_argument("--role", default="admin", choices=["admin", "analyst", "reviewer"])
    ap.add_argument("--company-name", required=True,
                    help="Name of the company this admin belongs to.")
    ap.add_argument("--create-company", action="store_true",
                    help="Create the company if it does not already exist.")
    ap.add_argument("--industry", default=None)
    ap.add_argument("--size", default=None)
    ap.add_argument("--use-case", default=None)
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        # ---- Resolve or create the company ----
        company = db.query(Company).filter(Company.name == args.company_name).first()
        if company is None:
            if not args.create_company:
                print(
                    f"[error] company '{args.company_name}' not found. "
                    f"Pass --create-company to create it here."
                )
                sys.exit(1)
            company = Company(
                name=args.company_name,
                industry=args.industry,
                size=args.size,
                use_case=args.use_case,
                is_active=True,
            )
            db.add(company)
            db.flush()
            print(f"[ok] created company id={company.id}, name={company.name}")
        else:
            print(f"[found] company id={company.id}, name={company.name}")

        # ---- Create or skip the user ----
        existing = db.query(User).filter(User.email == args.email).first()
        if existing:
            print(
                f"[skip] user with email {args.email} already exists "
                f"(id={existing.id}, role={existing.role}, "
                f"company_id={existing.company_id})"
            )
            return

        u = User(
            email=args.email,
            hashed_password=hash_password(args.password),
            full_name=args.full_name,
            role=args.role,
            is_active=True,
            company_id=company.id,   # ← the previous bug: this was missing
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        print(
            f"[ok] created user id={u.id}, email={u.email}, role={u.role}, "
            f"company_id={u.company_id} ({company.name})"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
