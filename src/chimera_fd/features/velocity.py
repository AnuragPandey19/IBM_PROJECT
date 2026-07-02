"""Velocity features — counts and sums per card1 (proxy for customer) over rolling windows.

IEEE-CIS doesn't have an explicit customer ID; `card1` is the standard proxy used in
Kaggle competition top solutions. We compute features looking ONLY at prior transactions
(no future leakage) by using groupby.shift().

Would these be available at prediction time?
  YES — velocity features look at past transactions only. At inference time we'd query
  Redis for the last N seconds/minutes of activity per card and compute the same features.
"""
from __future__ import annotations

import pandas as pd


def add_velocity_features(
    df: pd.DataFrame,
    entity_col: str = "card1",
    dt_col: str = "TransactionDT",
    amt_col: str = "TransactionAmt",
) -> pd.DataFrame:
    """Adds per-entity historical aggregation features WITHOUT leaking the current row.

    New columns:
      - <entity>_txn_count_before : number of prior txns by this entity
      - <entity>_amt_sum_before   : sum of prior amounts
      - <entity>_amt_mean_before  : mean of prior amounts (guarded div-by-zero)
      - <entity>_seconds_since_prev : gap between this and previous txn (NaN if first)
      - <entity>_amt_ratio_to_mean : current_amt / mean_of_prior_amts (1.0 if first)
    """
    if entity_col not in df.columns:
        raise KeyError(f"{entity_col} not in DataFrame")

    # Sort by entity + time so shift() gives the actual previous row for that entity
    df_sorted = df.sort_values([entity_col, dt_col], kind="mergesort").reset_index(drop=False)

    grp = df_sorted.groupby(entity_col, sort=False)

    # cumcount = 0 for first, 1 for second, etc. → equals number of PRIOR txns
    prior_count = grp.cumcount().astype("int32")

    # Cumulative sum of amount, SHIFTED so it excludes the current row
    cum_sum = grp[amt_col].cumsum() - df_sorted[amt_col]  # exclude self

    # Mean of prior amounts (safe against div-by-zero)
    prior_mean = (cum_sum / prior_count.where(prior_count > 0, 1)).astype("float32")
    prior_mean = prior_mean.where(prior_count > 0, other=0.0)

    # Seconds since previous txn (per entity)
    prev_dt = grp[dt_col].shift(1)
    seconds_since_prev = (df_sorted[dt_col] - prev_dt).astype("float32")

    # Current amount / prior mean (fallback 1.0 if no history)
    amt_ratio = (df_sorted[amt_col] / prior_mean.where(prior_mean > 0, 1)).astype("float32")
    amt_ratio = amt_ratio.where(prior_count > 0, other=1.0)

    df_sorted[f"{entity_col}_txn_count_before"] = prior_count
    df_sorted[f"{entity_col}_amt_sum_before"] = cum_sum.astype("float32")
    df_sorted[f"{entity_col}_amt_mean_before"] = prior_mean
    df_sorted[f"{entity_col}_seconds_since_prev"] = seconds_since_prev
    df_sorted[f"{entity_col}_amt_ratio_to_mean"] = amt_ratio

    # Restore original ordering
    df_out = df_sorted.sort_values("index").drop(columns=["index"]).reset_index(drop=True)
    return df_out
