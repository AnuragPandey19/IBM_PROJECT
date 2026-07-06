"""Sparkov demo lookups service.

The training-time fitted encoders (LabelEncoder for gender/state/category,
TargetEncoder for merchant/city/job/zip) were NOT persisted to disk in the
training script. But the engineered test parquet contains BOTH the original
string values AND the encoded numeric values.

At startup we scan the parquet once and reconstruct the mappings:
  * merchant     -> merchant_target_enc   (float)
  * city         -> city_target_enc       (float)
  * job          -> job_target_enc        (float)
  * zip          -> zip_target_enc        (float)

For LabelEncoder columns (gender, state, category) we can't reconstruct the
string label from the int alone since the parquet has already dropped the
original strings. BUT the training LabelEncoder sorts alphabetically and
starts at 1 (0 = NA), so we hard-code the mapping using the well-documented
Sparkov universe:
  * gender:   1=F, 2=M
  * state:    the 50 US state 2-letter codes in alphabetical order
  * category: the 14 Sparkov merchant categories in alphabetical order

This is a demo-only shortcut — for production we would save the fitted
encoder objects alongside the model artifact. Documented as such in the
presentation's limitations slide.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from api.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Hard-coded LabelEncoder-order mappings (training used sorted() + start=1)
# ---------------------------------------------------------------------------

GENDER_STR_TO_INT: dict[str, int] = {"F": 1, "M": 2}
GENDER_INT_TO_STR: dict[int, str] = {v: k for k, v in GENDER_STR_TO_INT.items()}

# US state 2-letter codes present in Sparkov, alphabetical
STATE_CODES: list[str] = [
    "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL",
    "GA", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA",
    "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE",
    "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV",
    "WY",
]
STATE_STR_TO_INT: dict[str, int] = {s: i + 1 for i, s in enumerate(STATE_CODES)}
STATE_INT_TO_STR: dict[int, str] = {v: k for k, v in STATE_STR_TO_INT.items()}

# Sparkov's 14 canonical merchant categories, alphabetical
CATEGORY_LABELS: list[str] = [
    "entertainment", "food_dining", "gas_transport",
    "grocery_net", "grocery_pos",
    "health_fitness", "home", "kids_pets",
    "misc_net", "misc_pos",
    "personal_care",
    "shopping_net", "shopping_pos",
    "travel",
]
CATEGORY_STR_TO_INT: dict[str, int] = {c: i + 1 for i, c in enumerate(CATEGORY_LABELS)}
CATEGORY_INT_TO_STR: dict[int, str] = {v: k for k, v in CATEGORY_STR_TO_INT.items()}


class SparkovLookups:
    """Singleton lookups service. Access via get_sparkov_lookups()."""

    _instance: Optional["SparkovLookups"] = None

    def __init__(self):
        self.loaded: bool = False
        # Reconstructed target-encoder mappings
        self.merchant_te: dict[str, float] = {}
        self.city_te: dict[str, float] = {}
        self.job_te: dict[str, float] = {}
        self.zip_te: dict[int, float] = {}
        # For frontend dropdowns — a curated shortlist
        self.top_merchants: list[str] = []
        self.top_cities: list[dict] = []   # [{city, state_int, city_pop, lat, long}, ...]
        self.top_jobs: list[str] = []
        # Global mean target rate (fallback for unseen values)
        self.global_target_mean: float = 0.0

    def load(self, parquet_path: Optional[Path] = None) -> "SparkovLookups":
        if self.loaded:
            return self

        path = parquet_path or settings.sparkov_features_path
        if not path.exists():
            raise FileNotFoundError(f"Sparkov features parquet not found: {path}")

        log.info("Loading Sparkov lookups from %s ...", path)
        df = pd.read_parquet(path)

        # ---- Target-encoder mappings (merchant / city / job / zip) ----
        for str_col, enc_col, attr in [
            ("merchant", "merchant_target_enc", "merchant_te"),
            ("city", "city_target_enc", "city_te"),
            ("job", "job_target_enc", "job_te"),
        ]:
            if str_col in df.columns and enc_col in df.columns:
                mapping = df.dropna(subset=[str_col]).drop_duplicates(subset=[str_col]).set_index(str_col)[enc_col].to_dict()
                setattr(self, attr, {str(k): float(v) for k, v in mapping.items()})
                log.info("Loaded %d %s -> %s pairs", len(mapping), str_col, enc_col)

        if "zip" in df.columns and "zip_target_enc" in df.columns:
            mapping = df.dropna(subset=["zip"]).drop_duplicates(subset=["zip"]).set_index("zip")["zip_target_enc"].to_dict()
            self.zip_te = {int(k): float(v) for k, v in mapping.items()}
            log.info("Loaded %d zip -> zip_target_enc pairs", len(mapping))

        # Global fraud rate for unseen values (approx equal to global mean of TE cols)
        if "merchant_target_enc" in df.columns:
            self.global_target_mean = float(df["merchant_target_enc"].mean())

        # ---- Curated frontend dropdown lists (top N by frequency) ----
        if "merchant" in df.columns:
            top = df["merchant"].value_counts().head(80).index.tolist()
            self.top_merchants = [str(m) for m in top]

        if "city" in df.columns:
            top_cities_series = df["city"].value_counts().head(120).index.tolist()
            for city_name in top_cities_series:
                row = df[df["city"] == city_name].iloc[0]
                self.top_cities.append({
                    "city": str(city_name),
                    "state_int": int(row.get("state", 0)),
                    "city_pop": int(row.get("city_pop", 0)) if not pd.isna(row.get("city_pop")) else 0,
                    "lat": float(row.get("lat", 0.0)) if not pd.isna(row.get("lat")) else 0.0,
                    "long": float(row.get("long", 0.0)) if not pd.isna(row.get("long")) else 0.0,
                })

        if "job" in df.columns:
            top_jobs = df["job"].value_counts().head(60).index.tolist()
            self.top_jobs = [str(j) for j in top_jobs]

        self.loaded = True
        log.info("Sparkov lookups ready: %d merchants, %d cities, %d jobs",
                 len(self.merchant_te), len(self.city_te), len(self.job_te))
        return self

    # ---- Encoding lookups (with sensible fallbacks) ----

    def merchant_enc(self, merchant: str) -> float:
        return self.merchant_te.get(str(merchant), self.global_target_mean)

    def city_enc(self, city: str) -> float:
        return self.city_te.get(str(city), self.global_target_mean)

    def job_enc(self, job: str) -> float:
        return self.job_te.get(str(job), self.global_target_mean)

    def zip_enc(self, zip_code) -> float:
        try:
            return self.zip_te.get(int(zip_code), self.global_target_mean)
        except (TypeError, ValueError):
            return self.global_target_mean


def get_sparkov_lookups() -> SparkovLookups:
    if SparkovLookups._instance is None:
        SparkovLookups._instance = SparkovLookups()
    return SparkovLookups._instance
