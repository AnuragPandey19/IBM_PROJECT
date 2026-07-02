"""Basic tests for data loader + splitter. Run with: pytest tests/"""
import pandas as pd
import pytest

from chimera_fd.data.splitter import downsample_train, time_based_split


@pytest.fixture
def toy_df():
    """Deterministic tiny frame that mimics IEEE-CIS structure."""
    return pd.DataFrame({
        "TransactionID": range(100),
        "TransactionDT": range(100),          # already sorted ascending
        "TransactionAmt": [10.0 * i for i in range(100)],
        "isFraud": [1 if i % 20 == 0 else 0 for i in range(100)],   # 5% fraud
    })


def test_time_split_shapes(toy_df):
    tr, va, te = time_based_split(toy_df, time_col="TransactionDT",
                                  train_frac=0.7, val_frac=0.15, test_frac=0.15)
    assert len(tr) == 70
    assert len(va) == 15
    assert len(te) == 15


def test_time_split_no_leakage(toy_df):
    """Every train timestamp must be strictly less than every val/test timestamp."""
    tr, va, te = time_based_split(toy_df, time_col="TransactionDT",
                                  train_frac=0.7, val_frac=0.15, test_frac=0.15)
    assert tr["TransactionDT"].max() < va["TransactionDT"].min()
    assert va["TransactionDT"].max() < te["TransactionDT"].min()


def test_downsample_preserves_class_balance(toy_df):
    original_rate = toy_df["isFraud"].mean()
    small = downsample_train(toy_df, frac=0.5, random_state=42)
    assert len(small) == 50
    # allow small drift due to rounding
    assert abs(small["isFraud"].mean() - original_rate) < 0.03


def test_time_split_rejects_bad_fractions(toy_df):
    with pytest.raises(ValueError):
        time_based_split(toy_df, "TransactionDT",
                         train_frac=0.5, val_frac=0.3, test_frac=0.3)
