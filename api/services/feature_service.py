"""Turn a raw transaction dict into a model-ready DataFrame using the saved
feature pipeline from training.
"""
from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from api.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


class FeatureService:
    """Loads feature_pipeline.pkl once and reuses it for every request."""

    _instance: Optional["FeatureService"] = None

    def __init__(self):
        self.pipeline = None
        self.loaded: bool = False

    def load(self) -> "FeatureService":
        if self.loaded:
            return self
        p = settings.feature_pipeline_path
        if not p.exists():
            raise FileNotFoundError(f"Feature pipeline not found: {p}")
        with open(p, "rb") as f:
            self.pipeline = pickle.load(f)
        self.loaded = True
        log.info("Feature pipeline loaded from %s", p)
        return self

    def build(self, raw: dict[str, Any]) -> pd.DataFrame:
        """Take a raw transaction dict, return a single-row engineered DataFrame."""
        if not self.loaded:
            self.load()
        df = pd.DataFrame([raw])
        # Feature pipeline expects TransactionDT to be numeric
        if "TransactionDT" not in df.columns:
            df["TransactionDT"] = 0
        # Ensure isFraud column exists (pipeline may reference it during training-mode transforms;
        # here it's ignored at inference — filled with a placeholder)
        if "isFraud" not in df.columns:
            df["isFraud"] = 0
        return self.pipeline.transform(df)


def get_feature_service() -> FeatureService:
    if FeatureService._instance is None:
        FeatureService._instance = FeatureService()
    return FeatureService._instance
