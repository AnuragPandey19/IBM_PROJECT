"""Augment the Sparkov training set with synthetic samples for the two
typologies the deployed model is empirically blind to:

  card_testing  — small-amount fraud on new cards at low-friction merchants
  velocity_spike — established customer suddenly spending 5-15x historical mean

WHY THIS EXISTS
---------------
V1+V2+V3 testing (150,714 rows, three independent authors) established that
the Sparkov-trained LightGBM catches 0% of card_testing patterns and 5% of
velocity_spike patterns. Root cause is training data under-representation:
the Sparkov generator does not model these typologies.

This script generates realistic augmentation rows drawn from the same feature
distributions Sparkov uses (real merchants, real cities, real jobs) and
appends them to the training parquet. The next train_sparkov.py run then
learns them.

USAGE
-----
    # Default: 3% card_testing + 3% velocity_spike augmentation
    python scripts/augment_sparkov_training.py

    # Custom fractions
    python scripts/augment_sparkov_training.py \
        --card-testing-frac 0.05 --velocity-spike-frac 0.05

    # Output goes to data/processed/sparkov/train_augmented.parquet.
    # train_sparkov.py should be pointed at this file for the next retrain.

DESIGN NOTES
------------
- All generated rows are labeled is_fraud=1. We're teaching the model that
  these patterns ARE fraud.
- We SAMPLE cc_num, merchant, city, job, zip from the actual training set so
  target-encoded features have real distributional support. Never invent
  identifiers that don't exist in the training vocabulary.
- Amounts, hours, and time-since-previous are drawn from typology-specific
  distributions (see _make_card_testing / _make_velocity_spike).
- Reproducible: `--seed 42` (default) guarantees identical output.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chimera_fd.config import load_config  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("augment_sparkov")


# --------------------------------------------------------------------------
# Typology generators
# --------------------------------------------------------------------------

_CARD_TESTING_CATEGORIES = [
    # Sparkov MCC codes the card_testing pattern most commonly targets.
    "misc_net",
    "entertainment",
    "misc_pos",
    "personal_care",
]


def _make_card_testing(base_df: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate N synthetic card_testing fraud rows.

    Pattern: small amount ($0.50-$8), new-looking cc_num, low-friction
    merchant category, spread across all hours (fraudsters test whenever).
    """
    # Sample cc_num from cards with the FEWEST prior transactions — closest
    # to "new card" that Sparkov training data actually contains. If Sparkov
    # has no "new" cards we still pick low-count cards as the best proxy.
    cc_counts = base_df.groupby("cc_num").size().sort_values()
    low_count_cards = cc_counts.head(max(n // 4, 100)).index.tolist()
    cc_choices = rng.choice(low_count_cards, size=n)

    # Sample merchant, city, job, zip from the actual training vocabulary
    # for the chosen categories only. This keeps target encoding valid.
    cat_mask = base_df["category"].isin(_CARD_TESTING_CATEGORIES)
    donor_pool = base_df[cat_mask]
    if len(donor_pool) < n:
        # Fall back to full pool if the category filter is too aggressive
        donor_pool = base_df
    donor_idx = rng.choice(len(donor_pool), size=n)
    donors = donor_pool.iloc[donor_idx].reset_index(drop=True)

    # Small amounts drawn from a heavy-lower-tail distribution
    amounts = rng.beta(1.2, 5.0, size=n) * 8.0 + 0.50  # ~$0.5 to $8
    amounts = np.round(amounts, 2)

    # Full 24-hour spread — card testing is not time-of-day-limited
    hours = rng.integers(0, 24, size=n)

    # Build rows by copying donor fields then overwriting the pattern-defining
    # ones. This guarantees every column expected by the training pipeline
    # is populated.
    rows = donors.copy()
    rows["cc_num"] = cc_choices
    rows["amt"] = amounts
    # Reconstruct unix_time so the hour extracted downstream matches
    # (Sparkov uses `((unix_time % 86400) // 3600)` for hour). Preserve the
    # donor's day-portion and just replace the hour-of-day.
    base_time = rows["unix_time"].astype("int64").values
    day_seconds = (base_time // 86400) * 86400
    rows["unix_time"] = (day_seconds + hours.astype("int64") * 3600).astype("int64")
    rows["is_fraud"] = 1
    return rows.reset_index(drop=True)


def _make_velocity_spike(base_df: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate N synthetic velocity_spike fraud rows.

    Pattern: existing cc_num with rich history (established customer),
    single transaction at 5x - 15x their historical mean amount, at
    varied hours + categories.
    """
    cc_counts = base_df.groupby("cc_num").size().sort_values(ascending=False)
    # Established customers: top-decile by transaction count
    top_decile = cc_counts.head(max(len(cc_counts) // 10, 100)).index.tolist()
    cc_choices = rng.choice(top_decile, size=n)

    # For each chosen card, compute historical mean amount from base_df
    hist_means = base_df.groupby("cc_num")["amt"].mean()
    mean_amounts = np.array([hist_means.get(c, 50.0) for c in cc_choices], dtype=float)

    # Sample ratios in [5, 15] with skew toward the lower end (realistic)
    ratios = 5.0 + rng.beta(1.5, 3.0, size=n) * 10.0
    spike_amounts = np.round(mean_amounts * ratios, 2)

    # Cap absurd amounts at $10000 (Sparkov training rarely goes above this)
    spike_amounts = np.minimum(spike_amounts, 10000.0)

    # Sample donor rows for other columns
    donor_idx = rng.choice(len(base_df), size=n)
    donors = base_df.iloc[donor_idx].reset_index(drop=True)

    rows = donors.copy()
    rows["cc_num"] = cc_choices
    rows["amt"] = spike_amounts
    rows["is_fraud"] = 1
    return rows.reset_index(drop=True)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=None,
                    help="Path to Sparkov training parquet. Default: derived "
                         "from chimera_fd config (data/processed/sparkov/train_features.parquet).")
    ap.add_argument("--output", type=Path, default=None,
                    help="Path to write the augmented parquet. Default: same "
                         "dir as input, named train_augmented.parquet.")
    ap.add_argument("--card-testing-frac", type=float, default=0.03,
                    help="Card-testing rows as fraction of input size. Default 0.03 (3 percent).")
    ap.add_argument("--velocity-spike-frac", type=float, default=0.03,
                    help="Velocity-spike rows as fraction of input size. Default 0.03 (3 percent).")
    ap.add_argument("--seed", type=int, default=42,
                    help="Random seed for reproducibility.")
    args = ap.parse_args()

    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "sparkov"

    in_path = args.input or (processed / "train_features.parquet")
    out_path = args.output or (processed / "train_augmented.parquet")

    if not in_path.exists():
        log.error("Input parquet not found: %s. Run scripts/build_features.py first.", in_path)
        return 2

    log.info("Loading training parquet: %s", in_path)
    df = pd.read_parquet(in_path)
    n_original = len(df)
    log.info("Loaded %d rows. Fraud rate: %.3f%%", n_original, 100 * df["is_fraud"].mean())

    rng = np.random.default_rng(args.seed)

    n_ct = int(n_original * args.card_testing_frac)
    n_vs = int(n_original * args.velocity_spike_frac)

    log.info("Generating %d card_testing samples...", n_ct)
    ct_rows = _make_card_testing(df, n_ct, rng)
    log.info("Generating %d velocity_spike samples...", n_vs)
    vs_rows = _make_velocity_spike(df, n_vs, rng)

    augmented = pd.concat([df, ct_rows, vs_rows], axis=0, ignore_index=True)
    log.info("Augmented total: %d rows (+%d = %.1f%% growth)",
             len(augmented), len(augmented) - n_original,
             100 * (len(augmented) - n_original) / n_original)
    log.info("New fraud rate: %.3f%%", 100 * augmented["is_fraud"].mean())

    # Shuffle so the fraud rows aren't all at the bottom (which would bias
    # train/val splits if the caller does a naive top-split).
    augmented = augmented.sample(frac=1.0, random_state=args.seed).reset_index(drop=True)

    log.info("Writing augmented parquet: %s", out_path)
    augmented.to_parquet(out_path, index=False)
    log.info("Done. Point train_sparkov.py at this file (or replace train_features.parquet).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
