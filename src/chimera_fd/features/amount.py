"""TransactionAmt features. Card-fraud amount distributions are heavy-tailed —
raw amount is a bad feature by itself; log-transform is essential."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_amount_features(df: pd.DataFrame, amt_col: str = "TransactionAmt") -> pd.DataFrame:
    """Adds:
      - log1p_amount   (natural log of 1+amount; log-normal-ish)
      - amount_cents   (fractional part; some fraud rings use exact whole amounts)
      - amount_bucket  (small=<$25, medium, large=>$500)
      - is_round_amount (1 if amount is a whole dollar — fraudsters often use round numbers)

    Would these be available at prediction time?
      YES — all derived from the incoming amount.
    """
    if amt_col not in df.columns:
        raise KeyError(f"{amt_col} not in DataFrame")

    amt = df[amt_col].astype("float32")

    out = df.copy()
    out["log1p_amount"] = np.log1p(amt).astype("float32")
    out["amount_cents"] = ((amt * 100).round().astype("int64") % 100).astype("int8")
    out["is_round_amount"] = (out["amount_cents"] == 0).astype("int8")

    # Amount bucket as categorical code (LightGBM likes small-int categoricals)
    bucket = pd.cut(amt, bins=[-np.inf, 25, 100, 500, np.inf],
                    labels=[0, 1, 2, 3]).astype("int8")
    out["amount_bucket"] = bucket
    return out
