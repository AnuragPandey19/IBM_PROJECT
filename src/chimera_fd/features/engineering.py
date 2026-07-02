"""Orchestrator: takes raw parquet → adds all engineered features → returns DataFrame.

Fit the encoders on TRAIN, then apply the same encoders on VAL and TEST.
"""
from __future__ import annotations

import logging

import pandas as pd

from chimera_fd.features.amount import add_amount_features
from chimera_fd.features.encoding import LabelEncoder, TargetEncoder
from chimera_fd.features.temporal import add_temporal_features
from chimera_fd.features.velocity import add_velocity_features

log = logging.getLogger(__name__)


# High-cardinality columns worth target-encoding (fit on train only)
TARGET_ENCODE_COLS = ["card1", "card2", "card3", "card5", "addr1", "P_emaildomain",
                      "R_emaildomain", "DeviceInfo"]

# Low-cardinality categoricals — label-encode
LABEL_ENCODE_COLS = ["ProductCD", "card4", "card6", "DeviceType", "id_12", "id_15",
                     "id_16", "id_23", "id_27", "id_28", "id_29", "id_30", "id_31",
                     "id_33", "id_34", "id_35", "id_36", "id_37", "id_38", "M1", "M2",
                     "M3", "M4", "M5", "M6", "M7", "M8", "M9"]

# Missingness of the whole identity block is a strong signal (~76% have no identity data)
IDENTITY_MARKER_COL = "id_01"


def add_missingness_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add a few key boolean 'was-this-field-missing' flags. Identity block absence
    is highly predictive."""
    out = df.copy()
    out["has_identity_info"] = out.get(IDENTITY_MARKER_COL, pd.Series(index=out.index)).notna().astype("int8")
    for col in ["DeviceInfo", "DeviceType", "P_emaildomain", "R_emaildomain"]:
        if col in out.columns:
            out[f"missing_{col}"] = out[col].isna().astype("int8")
    return out


class FeaturePipeline:
    """Fit on train → transform train/val/test with the same encoders."""

    def __init__(self):
        self.label_encoder = LabelEncoder()
        self.target_encoder = TargetEncoder(smoothing=20.0)
        self.target_col = "isFraud"

    def fit(self, train_df: pd.DataFrame) -> "FeaturePipeline":
        """Fit label + target encoders. Called ONCE on training data."""
        cols_present_le = [c for c in LABEL_ENCODE_COLS if c in train_df.columns]
        cols_present_te = [c for c in TARGET_ENCODE_COLS if c in train_df.columns]
        log.info("Fitting LabelEncoder on %d columns", len(cols_present_le))
        self.label_encoder.fit(train_df, cols_present_le)
        log.info("Fitting TargetEncoder on %d columns", len(cols_present_te))
        self.target_encoder.fit(train_df, cols_present_te, target_col=self.target_col)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply feature engineering to any split (train/val/test)."""
        log.info("Adding temporal features...")
        df = add_temporal_features(df)
        log.info("Adding amount features...")
        df = add_amount_features(df)
        log.info("Adding velocity features (card1)...")
        df = add_velocity_features(df, entity_col="card1")
        log.info("Adding missingness flags...")
        df = add_missingness_flags(df)
        log.info("Applying LabelEncoder...")
        df = self.label_encoder.transform(df)
        log.info("Applying TargetEncoder...")
        df = self.target_encoder.transform(df)
        log.info("Done. Final shape: %s", df.shape)
        return df

    def fit_transform(self, train_df: pd.DataFrame) -> pd.DataFrame:
        self.fit(train_df)
        return self.transform(train_df)


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the list of column names that should be used as MODEL INPUTS.
    Drops the label, ID columns, and any remaining object columns that weren't encoded."""
    drop = {"isFraud", "TransactionID"}
    keep = []
    for col in df.columns:
        if col in drop:
            continue
        if df[col].dtype == "object":
            # Anything not encoded is unusable in LightGBM; skip it
            continue
        keep.append(col)
    return keep
