"""Sparkov feature engineering pipeline.

Sparkov has a completely different feature space from IEEE-CIS. This module
builds equivalent-TYPE features (temporal, amount, velocity, categorical
encoding, geographic) from Sparkov's own columns.

The point of the Sparkov test isn't feature-level transfer — feature spaces
don't match. It is METHODOLOGY transfer: does our same design (LightGBM +
velocity + target encoding + no-SMOTE + cost-sensitive weighting) also work
on a completely different dataset? If yes, methodology generalizes.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from chimera_fd.features.encoding import LabelEncoder, TargetEncoder

log = logging.getLogger(__name__)


# Categorical columns in Sparkov (label-encode)
SPARKOV_LABEL_COLS = ["gender", "state", "category"]

# High-cardinality categoricals (target-encode)
SPARKOV_TARGET_COLS = ["merchant", "city", "job", "zip"]


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance in km between two lat/long points (broadcast-friendly)."""
    R = 6371.0
    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)
    dlat = lat2 - lat1
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def add_sparkov_temporal(df: pd.DataFrame) -> pd.DataFrame:
    """Hour, day-of-week, weekend, night from unix_time."""
    out = df.copy()
    ts = df["unix_time"].astype("int64")
    out["hour"] = ((ts % 86400) // 3600).astype("int8")
    out["day_of_week"] = ((ts // 86400) % 7).astype("int8")
    out["is_weekend"] = (out["day_of_week"] >= 5).astype("int8")
    out["is_night"] = (out["hour"] < 6).astype("int8")
    return out


def add_sparkov_amount(df: pd.DataFrame) -> pd.DataFrame:
    """Log amount, amount cents, round-amount flag, bucket."""
    out = df.copy()
    amt = df["amt"].astype("float32")
    out["log1p_amt"] = np.log1p(amt).astype("float32")
    out["amt_cents"] = ((amt * 100).round().astype("int64") % 100).astype("int8")
    out["is_round_amt"] = (out["amt_cents"] == 0).astype("int8")
    out["amt_bucket"] = pd.cut(amt, bins=[-np.inf, 25, 100, 500, np.inf],
                               labels=[0, 1, 2, 3]).astype("int8")
    return out


def add_sparkov_geographic(df: pd.DataFrame) -> pd.DataFrame:
    """Distance between customer and merchant coordinates. IEEE-CIS doesn't have
    this — Sparkov's biggest structural signal that our methodology can use."""
    out = df.copy()
    out["cust_merch_dist_km"] = haversine_km(
        df["lat"].values, df["long"].values,
        df["merch_lat"].values, df["merch_long"].values,
    ).astype("float32")
    # Age of cardholder (proxy: transaction year - birth year)
    dob_year = pd.to_datetime(df["dob"], errors="coerce").dt.year
    trans_year = pd.to_datetime(df["trans_date_trans_time"], errors="coerce").dt.year
    out["cust_age"] = (trans_year - dob_year).fillna(40).astype("int16")
    return out


def add_sparkov_velocity(df: pd.DataFrame,
                         entity_col: str = "cc_num",
                         dt_col: str = "unix_time",
                         amt_col: str = "amt") -> pd.DataFrame:
    """Per-cc_num velocity features (analog to per-card1 in IEEE-CIS)."""
    df_sorted = df.sort_values([entity_col, dt_col], kind="mergesort").reset_index(drop=False)
    grp = df_sorted.groupby(entity_col, sort=False)

    prior_count = grp.cumcount().astype("int32")
    cum_sum = grp[amt_col].cumsum() - df_sorted[amt_col]
    prior_mean = (cum_sum / prior_count.where(prior_count > 0, 1)).astype("float32")
    prior_mean = prior_mean.where(prior_count > 0, other=0.0)
    prev_dt = grp[dt_col].shift(1)
    seconds_since_prev = (df_sorted[dt_col] - prev_dt).astype("float32")
    amt_ratio = (df_sorted[amt_col] / prior_mean.where(prior_mean > 0, 1)).astype("float32")
    amt_ratio = amt_ratio.where(prior_count > 0, other=1.0)

    df_sorted[f"{entity_col}_txn_count_before"] = prior_count
    df_sorted[f"{entity_col}_amt_sum_before"] = cum_sum.astype("float32")
    df_sorted[f"{entity_col}_amt_mean_before"] = prior_mean
    df_sorted[f"{entity_col}_seconds_since_prev"] = seconds_since_prev
    df_sorted[f"{entity_col}_amt_ratio_to_mean"] = amt_ratio

    return df_sorted.sort_values("index").drop(columns=["index"]).reset_index(drop=True)


class SparkovFeaturePipeline:
    """Fit-on-train / transform-any-split pipeline for Sparkov."""

    def __init__(self):
        self.label_encoder = LabelEncoder()
        self.target_encoder = TargetEncoder(smoothing=20.0)
        self.target_col = "is_fraud"

    def fit(self, train_df: pd.DataFrame) -> "SparkovFeaturePipeline":
        cols_le = [c for c in SPARKOV_LABEL_COLS if c in train_df.columns]
        cols_te = [c for c in SPARKOV_TARGET_COLS if c in train_df.columns]
        log.info("Sparkov LabelEncoder on %d cols, TargetEncoder on %d cols",
                 len(cols_le), len(cols_te))
        self.label_encoder.fit(train_df, cols_le)
        self.target_encoder.fit(train_df, cols_te, target_col=self.target_col)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        log.info("Sparkov transform: temporal...")
        df = add_sparkov_temporal(df)
        log.info("Sparkov transform: amount...")
        df = add_sparkov_amount(df)
        log.info("Sparkov transform: geographic...")
        df = add_sparkov_geographic(df)
        log.info("Sparkov transform: velocity (cc_num)...")
        df = add_sparkov_velocity(df)
        log.info("Sparkov transform: label encoding...")
        df = self.label_encoder.transform(df)
        log.info("Sparkov transform: target encoding...")
        df = self.target_encoder.transform(df)
        log.info("Sparkov final shape: %s", df.shape)
        return df

    def fit_transform(self, train_df: pd.DataFrame) -> pd.DataFrame:
        self.fit(train_df)
        return self.transform(train_df)


def get_sparkov_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return usable model-input columns for Sparkov."""
    # Drop the label + string/date columns that aren't encoded
    drop = {
        "is_fraud", "trans_num", "trans_date_trans_time", "dob",
        "first", "last", "street",   # PII we don't use as features
        "merchant", "city", "job", "zip",   # already target-encoded → use *_target_enc
    }
    keep = []
    for col in df.columns:
        if col in drop:
            continue
        if df[col].dtype == "object":
            continue
        keep.append(col)
    return keep
