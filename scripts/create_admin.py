"""Bootstrap the first admin user.

Usage:
    python scripts/create_admin.py --email admin@chimera.local --password strongpass123
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from api.db.models import User
from api.db.session import SessionLocal, init_db
from api.security import hash_password


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--full-name", default="Admin User")
    ap.add_argument("--role", default="admin", choices=["admin", "analyst", "reviewer"])
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == args.email).first()
        if existing:
            print(f"[skip] user with email {args.email} already exists (id={existing.id}, role={existing.role})")
            return

        u = User(
            email=args.email,
            hashed_password=hash_password(args.password),
            full_name=args.full_name,
            role=args.role,
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        print(f"[ok] created user id={u.id}, email={u.email}, role={u.role}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
