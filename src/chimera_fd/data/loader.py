"""Load raw IEEE-CIS and Sparkov CSVs and merge them into working DataFrames.

Key decisions:
- IEEE-CIS transaction and identity tables are merged on TransactionID with a LEFT join.
  Not every transaction has an identity row (~24% do). NaNs in identity columns are expected.
- We use pandas read_csv with sensible dtypes to save memory on the wide IEEE-CIS table.
- Sparkov comes with its own train/test split already; we load them separately.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# IEEE-CIS
# --------------------------------------------------------------------------
def load_ieee_cis(
    transaction_path: str | Path,
    identity_path: str | Path,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Load IEEE-CIS transaction + identity CSVs and merge.

    Args:
        transaction_path: path to train_transaction.csv (or test_transaction.csv)
        identity_path:    path to train_identity.csv (or test_identity.csv)
        nrows: if set, only read the first N rows (useful for smoke tests)

    Returns:
        Single DataFrame with all transaction columns plus identity columns.
        isFraud column present only for the training split.
    """
    tx_path = Path(transaction_path)
    id_path = Path(identity_path)
    if not tx_path.exists():
        raise FileNotFoundError(f"Transaction file not found: {tx_path}")
    if not id_path.exists():
        raise FileNotFoundError(f"Identity file not found: {id_path}")

    logger.info("Reading transaction table: %s", tx_path)
    tx = pd.read_csv(tx_path, nrows=nrows)
    logger.info("Transaction rows: %d, cols: %d", len(tx), tx.shape[1])

    logger.info("Reading identity table: %s", id_path)
    ident = pd.read_csv(id_path, nrows=nrows)
    logger.info("Identity rows: %d, cols: %d", len(ident), ident.shape[1])

    logger.info("Merging on TransactionID (left join)")
    merged = tx.merge(ident, how="left", on="TransactionID")
    logger.info(
        "Merged rows: %d, cols: %d. Identity match rate: %.1f%%",
        len(merged),
        merged.shape[1],
        100.0 * ident.shape[0] / len(merged),
    )
    return merged


# --------------------------------------------------------------------------
# Sparkov
# --------------------------------------------------------------------------
def load_sparkov(
    train_path: str | Path,
    test_path: str | Path,
    nrows: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load Sparkov train and test CSVs.

    Sparkov is our cross-dataset validation set. Different schema from IEEE-CIS.
    Common columns: trans_date_trans_time, cc_num, merchant, category, amt,
                    first, last, gender, street, city, state, zip,
                    lat, long, city_pop, job, dob, trans_num,
                    unix_time, merch_lat, merch_long, is_fraud
    """
    train_path = Path(train_path)
    test_path = Path(test_path)
    if not train_path.exists():
        raise FileNotFoundError(f"Sparkov train file not found: {train_path}")
    if not test_path.exists():
        raise FileNotFoundError(f"Sparkov test file not found: {test_path}")

    logger.info("Reading Sparkov train: %s", train_path)
    train_df = pd.read_csv(train_path, nrows=nrows)
    logger.info("Sparkov train rows: %d, fraud rate: %.3f%%",
                len(train_df), 100.0 * train_df["is_fraud"].mean())

    logger.info("Reading Sparkov test: %s", test_path)
    test_df = pd.read_csv(test_path, nrows=nrows)
    logger.info("Sparkov test rows: %d, fraud rate: %.3f%%",
                len(test_df), 100.0 * test_df["is_fraud"].mean())

    # Drop the anonymous index column that pandas produces from Sparkov's leading comma
    for df in (train_df, test_df):
        if df.columns[0].startswith("Unnamed") or df.columns[0] == "":
            df.drop(columns=[df.columns[0]], inplace=True)

    return train_df, test_df


# --------------------------------------------------------------------------
# Convenience: read a saved parquet file
# --------------------------------------------------------------------------
def load_parquet(path: str | Path) -> pd.DataFrame:
    """Read a processed parquet file. Faster and smaller than CSV."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")
    return pd.read_parquet(path)
