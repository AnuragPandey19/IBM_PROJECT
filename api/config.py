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

    # ---- Redis (velocity cache) — STUB SETTINGS ----
    # These are declared so the roadmap change ("move per-card velocity
    # features into a Redis cache") doesn't need a schema migration. Right
    # now nothing reads them; velocity features are computed in-process by
    # `add_velocity_features()`. Left here intentionally as a hook for
    # future work.
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    # ---- Model artifacts ----
    models_dir: Path = PROJECT_ROOT / "models"
    stage1_model_path: Path = PROJECT_ROOT / "models" / "stage1_lightgbm.pkl"
    stage3_calibrator_path: Path = PROJECT_ROOT / "models" / "stage3_isotonic.pkl"
    feature_pipeline_path: Path = PROJECT_ROOT / "data" / "processed" / "ieee_cis" / "feature_pipeline.pkl"

    # Sparkov mode (human-interpretable fraud detection)
    stage1_sparkov_path: Path = PROJECT_ROOT / "models" / "stage1_sparkov.pkl"
    sparkov_features_path: Path = PROJECT_ROOT / "data" / "processed" / "sparkov" / "test_features.parquet"

    # ---- Decision thresholds (cascade routing) ----
    approve_below: float = 0.05      # P < 0.05 -> auto-approve
    block_above: float = 0.95        # P > 0.95 -> auto-block
    default_threshold: float = 0.40  # For binary decision if no calibration

    # ---- Safety-net rules (decision augmenter) --------------------------
    # Post-model rules that patch known blind spots identified by V1+V2+V3
    # testing. Each rule is independently toggleable via env var so ops can
    # disable a misbehaving rule without a code change. See
    # api/services/decision_augmenter.py for the rule bodies and
    # MODEL_AUDIT_POST_TESTING.md for the empirical justification.
    enable_safety_net_card_testing: bool = True     # push tiny-amount
                                                     # new-customer misc
                                                     # transactions -> review
    enable_safety_net_velocity_spike: bool = True   # push established-customer
                                                     # sudden-large-spend -> review
    enable_safety_net_night_new_high: bool = True   # push new-customer
                                                     # evening high-amount -> review

    # Thresholds for the rules — expose so they can be tuned via env vars
    # in production once real fraud statistics are available.
    safety_net_card_testing_max_amount: float = 10.0
    safety_net_velocity_spike_ratio: float = 5.0
    safety_net_night_new_high_min_amount: float = 1000.0

    # ---- Auth ----
    jwt_secret_key: str = "change-me-in-prod-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 8   # 8 hours

    # ---- CORS ----
    # Localhost origins are always allowed for dev. Add production origins via
    # the CORS_ORIGINS env var (comma-separated) — pydantic-settings will parse
    # a JSON list or a comma-separated string.
    #   Example: CORS_ORIGINS='["https://undebuggedbit-chimera-fd.hf.space"]'
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        # HF Space same-origin production URL (frontend served from same host,
        # but keep this here so a separately-hosted frontend can still be added).
        "https://undebuggedbit-chimera-fd.hf.space",
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
