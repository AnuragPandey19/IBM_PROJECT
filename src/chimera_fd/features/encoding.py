"""Categorical encoding.

For LightGBM we mostly use label encoding — it handles categoricals natively via the
`categorical_feature` argument. For very high-cardinality columns (card1, addr1, etc.)
we ALSO compute target encoding fit on TRAIN ONLY to avoid target leakage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class LabelEncoder:
    """Simple label encoder that treats NaN as its own category (integer 0)."""

    def __init__(self):
        self.mappings: dict[str, dict] = {}

    def fit(self, df: pd.DataFrame, cols: list[str]) -> "LabelEncoder":
        for col in cols:
            if col not in df.columns:
                continue
            unique = df[col].astype("object").fillna("__NA__").unique()
            self.mappings[col] = {val: i + 1 for i, val in enumerate(sorted(map(str, unique)))}
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col, mapping in self.mappings.items():
            if col not in out.columns:
                continue
            out[col] = (
                out[col].astype("object").fillna("__NA__").astype(str).map(mapping).fillna(0).astype("int32")
            )
        return out


class TargetEncoder:
    """Smoothed target encoder. Encodes each category as the smoothed mean fraud rate.

    Fitted on TRAIN ONLY. Applied to val/test using the fit mappings.
    """

    def __init__(self, smoothing: float = 20.0):
        self.smoothing = smoothing
        self.global_mean: float = 0.0
        self.mappings: dict[str, pd.Series] = {}

    def fit(self, df: pd.DataFrame, cols: list[str], target_col: str) -> "TargetEncoder":
        self.global_mean = float(df[target_col].mean())
        for col in cols:
            if col not in df.columns:
                continue
            grp = df.groupby(col)[target_col]
            counts = grp.count()
            means = grp.mean()
            smoothed = (counts * means + self.smoothing * self.global_mean) / (
                counts + self.smoothing
            )
            self.mappings[col] = smoothed.astype("float32")
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col, mapping in self.mappings.items():
            if col not in out.columns:
                continue
            out[f"{col}_target_enc"] = (
                out[col].map(mapping).fillna(self.global_mean).astype("float32")
            )
        return out
