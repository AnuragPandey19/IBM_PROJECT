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

# SQLite needs check_same_thread=False for FastAPI's threaded workers
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
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
    """Create all tables. Called on app startup (or use Alembic in prod)."""
    from api.db.base import Base
    # Import models so their tables register with Base.metadata
    from api.db import models  # noqa: F401
    log.info("Creating tables in %s", settings.database_url.split("@")[-1])
    Base.metadata.create_all(bind=engine)
    log.info("Tables ready.")
