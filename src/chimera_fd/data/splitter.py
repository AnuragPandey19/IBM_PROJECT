"""Time-based splitting. Random splits on time-series fraud data are a common capstone
failure mode: they leak future information into training and inflate offline metrics.
This module refuses to do a random split on timestamped data.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def time_based_split(
    df: pd.DataFrame,
    time_col: str,
    train_frac: float = 0.80,
    val_frac: float = 0.10,
    test_frac: float = 0.10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split df into train / val / test by chronological quantiles of `time_col`.

    The three fractions must sum to 1.0.

    Returns:
        (train_df, val_df, test_df), each sorted by time_col ascending.
    """
    total = train_frac + val_frac + test_frac
    if not (0.99 < total < 1.01):
        raise ValueError(
            f"Fractions must sum to 1.0, got {total:.3f} "
            f"(train={train_frac}, val={val_frac}, test={test_frac})"
        )
    if time_col not in df.columns:
        raise KeyError(f"time_col '{time_col}' not in DataFrame columns")

    logger.info("Sorting %d rows by %s", len(df), time_col)
    df_sorted = df.sort_values(time_col, kind="mergesort").reset_index(drop=True)

    n = len(df_sorted)
    train_end = int(n * train_frac)
    val_end = train_end + int(n * val_frac)

    train_df = df_sorted.iloc[:train_end].copy()
    val_df = df_sorted.iloc[train_end:val_end].copy()
    test_df = df_sorted.iloc[val_end:].copy()

    logger.info(
        "Split sizes: train=%d (%.1f%%), val=%d (%.1f%%), test=%d (%.1f%%)",
        len(train_df), 100.0 * len(train_df) / n,
        len(val_df),   100.0 * len(val_df)   / n,
        len(test_df),  100.0 * len(test_df)  / n,
    )

    # Report class balance per split to catch degenerate splits early
    if "isFraud" in df_sorted.columns:
        for name, part in [("train", train_df), ("val", val_df), ("test", test_df)]:
            fr = part["isFraud"].mean() * 100
            logger.info("Fraud rate in %s: %.3f%% (n=%d)", name, fr, len(part))
    elif "is_fraud" in df_sorted.columns:  # Sparkov naming
        for name, part in [("train", train_df), ("val", val_df), ("test", test_df)]:
            fr = part["is_fraud"].mean() * 100
            logger.info("Fraud rate in %s: %.3f%% (n=%d)", name, fr, len(part))

    return train_df, val_df, test_df


def downsample_train(df: pd.DataFrame, frac: float, random_state: int = 42) -> pd.DataFrame:
    """Downsample the training set for faster iteration during development.

    STRATIFIES by isFraud (or is_fraud) so the class balance is preserved.
    NEVER call this on val or test.
    """
    if frac >= 1.0:
        return df

    label_col = "isFraud" if "isFraud" in df.columns else "is_fraud" if "is_fraud" in df.columns else None
    if label_col is None:
        logger.warning("No fraud label column found; downsampling without stratification")
        return df.sample(frac=frac, random_state=random_state).reset_index(drop=True)

    parts = []
    for label_val, group in df.groupby(label_col):
        parts.append(group.sample(frac=frac, random_state=random_state))
    out = pd.concat(parts, axis=0).sort_index().reset_index(drop=True)
    logger.info(
        "Downsampled train from %d → %d rows (frac=%.2f). Fraud rate preserved: %.3f%%",
        len(df), len(out), frac, out[label_col].mean() * 100,
    )
    return out
