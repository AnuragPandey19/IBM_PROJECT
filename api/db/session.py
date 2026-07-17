"""Database engine + session factory.

Uses SQLite by default (data/api.db) so nothing external is required to run.
Set DATABASE_URL env var to point at PostgreSQL for production.
"""
from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings

log = logging.getLogger(__name__)

settings = get_settings()

# Defensive: HF Space secrets sometimes come through as empty string when unset.
# Fall back to SQLite in that case so the container at least starts.
_db_url = (settings.database_url or "").strip()
if not _db_url or "://" not in _db_url:
    log.warning(
        "DATABASE_URL is empty or malformed (%r) — falling back to SQLite. "
        "Set DATABASE_URL as a Space secret to use PostgreSQL.",
        settings.database_url,
    )
    _db_url = "sqlite:////tmp/chimera_fallback.db"

# Normalise the Render / Heroku convention of "postgres://" → "postgresql://"
if _db_url.startswith("postgres://"):
    _db_url = "postgresql://" + _db_url[len("postgres://"):]

log.info("Using database: %s", _db_url.split("@")[-1])

# SQLite needs check_same_thread=False for FastAPI's threaded workers
connect_args = {}
if _db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    _db_url,
    echo=settings.debug and settings.env == "dev",
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session that closes automatically."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Called on app startup (or use Alembic in prod).

    Also runs a lightweight column-only migration: after create_all(), we
    inspect each table's actual columns vs the model's declared columns and
    ALTER TABLE ADD COLUMN for any missing ones. This lets us add nullable
    columns to models without needing a full Alembic setup — safe both on
    fresh SQLite and existing Postgres.

    Explicitly NOT supported by this lightweight migrator:
      - column removals (never auto-drop)
      - column type changes (would need actual DDL, use Alembic)
      - NOT-NULL columns (auto-add would fail on existing rows)
      - constraint changes
    """
    from sqlalchemy import inspect, text
    from sqlalchemy.exc import OperationalError, ProgrammingError

    from api.db.base import Base
    from api.db import models  # noqa: F401 — registers tables

    log.info("Creating tables in %s", _db_url.split("@")[-1])
    Base.metadata.create_all(bind=engine)

    # ---- Lightweight ADD COLUMN migration ---------------------------
    # Runs on every startup, idempotent. Compares model columns to DB
    # columns and adds any missing nullable ones. Enables safe schema
    # evolution for the audit-driven changes (e.g. rules_triggered on
    # predictions) without a full Alembic setup.
    inspector = inspect(engine)
    added: list[str] = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                # Skip primary keys (should already exist from create_all)
                if col.primary_key:
                    continue
                # Only auto-add nullable columns — non-nullable ADD would
                # fail on existing rows.
                if not col.nullable:
                    log.warning("Skipping non-null column %s.%s (needs manual migration)",
                                table.name, col.name)
                    continue
                # Compile the column type for the current dialect
                col_type = col.type.compile(dialect=engine.dialect)
                stmt = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}'
                try:
                    conn.execute(text(stmt))
                    added.append(f"{table.name}.{col.name}")
                    log.info("Added missing column: %s.%s", table.name, col.name)
                except (OperationalError, ProgrammingError) as e:
                    log.warning("Failed to add column %s.%s: %s",
                                table.name, col.name, e)

    if added:
        log.info("Auto-migration added %d columns: %s", len(added), added)
    log.info("Tables ready.")
