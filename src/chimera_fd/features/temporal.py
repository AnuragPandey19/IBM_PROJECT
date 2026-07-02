"""Time-derived features. TransactionDT in IEEE-CIS is seconds since an unknown reference
date. That reference is opaque, but hour-of-day, day-of-week, weekend, and night flags
are all derivable and are strong signals in card fraud."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_temporal_features(df: pd.DataFrame, dt_col: str = "TransactionDT") -> pd.DataFrame:
    """Adds:
      - hour        (0-23)
      - day_of_week (0-6, Mon=0 by convention — but reference is unknown so it's still just a modulus)
      - is_weekend  (1 if dow in {5, 6})
      - is_night    (1 if hour in [0, 6))
      - days_since_start (relative to earliest txn in this frame; captures dataset drift)

    Would these be available at prediction time?
      YES — all derived from the incoming transaction timestamp.
    """
    if dt_col not in df.columns:
        raise KeyError(f"{dt_col} not in DataFrame")

    dt = df[dt_col].astype("int64")

    out = df.copy()
    out["hour"] = ((dt % 86400) // 3600).astype("int8")
    out["day_of_week"] = ((dt // 86400) % 7).astype("int8")
    out["is_weekend"] = (out["day_of_week"] >= 5).astype("int8")
    out["is_night"] = (out["hour"] < 6).astype("int8")
    out["days_since_start"] = ((dt - dt.min()) // 86400).astype("int32")
    return out
