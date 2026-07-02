"""API configuration. All settings driven by environment variables so the same
image can run in dev, staging, and prod with only .env changes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # ---- Environment ----
    env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = True

    # ---- App identity ----
    app_name: str = "CHIMERA-FD Fraud Detection API"
    app_version: str = "0.1.0"

    # ---- Server ----
    host: str = "0.0.0.0"
    port: int = 8000

    # ---- Database ----
    # For local dev without Postgres, defaults to SQLite file
    database_url: str = Field(
        default=f"sqlite:///{PROJECT_ROOT}/data/api.db",
        description="SQLAlchemy connection string. Use postgresql://user:pass@host/db in prod.",
    )

    # ---- Redis (velocity cache) ----
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False   # Set true when Redis is available

    # ---- Model artifacts ----
    models_dir: Path = PROJECT_ROOT / "models"
    stage1_model_path: Path = PROJECT_ROOT / "models" / "stage1_lightgbm.pkl"
    stage3_calibrator_path: Path = PROJECT_ROOT / "models" / "stage3_isotonic.pkl"
    feature_pipeline_path: Path = PROJECT_ROOT / "data" / "processed" / "ieee_cis" / "feature_pipeline.pkl"

    # ---- Decision thresholds (cascade routing) ----
    approve_below: float = 0.05      # P < 0.05 -> auto-approve
    block_above: float = 0.95        # P > 0.95 -> auto-block
    default_threshold: float = 0.40  # For binary decision if no calibration

    # ---- Auth ----
    jwt_secret_key: str = "change-me-in-prod-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 8   # 8 hours

    # ---- CORS ----
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ]

    # ---- Logging ----
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
