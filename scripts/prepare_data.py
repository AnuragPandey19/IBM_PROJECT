"""One-command data preparation script.

Reads raw IEEE-CIS CSVs, merges transaction+identity, splits by time,
saves train/val/test parquet files to data/processed/.

Usage (from project root):
    python scripts/prepare_data.py                    # full pipeline
    python scripts/prepare_data.py --nrows 50000      # quick smoke test
    python scripts/prepare_data.py --dataset sparkov  # prep Sparkov instead
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add src/ to path so we can import chimera_fd without installing
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chimera_fd.config import load_config
from chimera_fd.data.loader import load_ieee_cis, load_sparkov
from chimera_fd.data.splitter import downsample_train, time_based_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prepare_data")


def prepare_ieee_cis(cfg, nrows: int | None):
    """Full IEEE-CIS prep: merge → time split → save parquet."""
    t0 = time.time()

    log.info("=" * 60)
    log.info("IEEE-CIS pipeline")
    log.info("=" * 60)

    merged = load_ieee_cis(
        cfg.data.ieee_cis.train_transaction,
        cfg.data.ieee_cis.train_identity,
        nrows=nrows,
    )
    log.info("Overall fraud rate: %.3f%%", 100.0 * merged["isFraud"].mean())

    # Time-based split
    train_df, val_df, test_df = time_based_split(
        merged,
        time_col="TransactionDT",
        train_frac=cfg.split.train_frac,
        val_frac=cfg.split.val_frac,
        test_frac=cfg.split.test_frac,
    )

    # Optional downsample of train for iteration speed
    downsample_frac = cfg.split.get("train_downsample_frac")
    if downsample_frac is not None and downsample_frac < 1.0:
        log.info("Downsampling train to frac=%.2f", downsample_frac)
        train_df = downsample_train(train_df, frac=downsample_frac,
                                    random_state=cfg.random_seed)

    # Save
    out_dir = Path(cfg.data.processed_dir) / "ieee_cis"
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("Writing parquet to %s", out_dir)

    train_df.to_parquet(out_dir / "train.parquet", index=False)
    val_df.to_parquet(out_dir / "val.parquet", index=False)
    test_df.to_parquet(out_dir / "test.parquet", index=False)

    log.info("Done in %.1f seconds.", time.time() - t0)
    log.info("Files written:")
    for p in sorted(out_dir.glob("*.parquet")):
        size_mb = p.stat().st_size / (1024 * 1024)
        log.info("  %s (%.1f MB)", p.name, size_mb)


def prepare_sparkov(cfg, nrows: int | None):
    """Sparkov prep: load train/test as-is (already split), save parquet."""
    t0 = time.time()

    log.info("=" * 60)
    log.info("Sparkov pipeline")
    log.info("=" * 60)

    train_df, test_df = load_sparkov(
        cfg.data.sparkov.train,
        cfg.data.sparkov.test,
        nrows=nrows,
    )

    out_dir = Path(cfg.data.processed_dir) / "sparkov"
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("Writing parquet to %s", out_dir)

    train_df.to_parquet(out_dir / "train.parquet", index=False)
    test_df.to_parquet(out_dir / "test.parquet", index=False)

    log.info("Done in %.1f seconds.", time.time() - t0)
    log.info("Files written:")
    for p in sorted(out_dir.glob("*.parquet")):
        size_mb = p.stat().st_size / (1024 * 1024)
        log.info("  %s (%.1f MB)", p.name, size_mb)


def main():
    ap = argparse.ArgumentParser(description="Prepare CHIMERA-FD data")
    ap.add_argument("--dataset", choices=["ieee_cis", "sparkov", "both"],
                    default="ieee_cis", help="Which dataset to prepare")
    ap.add_argument("--nrows", type=int, default=None,
                    help="Read only N rows for a quick smoke test")
    ap.add_argument("--config", default=None,
                    help="Alternate config file path")
    args = ap.parse_args()

    cfg = load_config(args.config)

    if args.dataset in ("ieee_cis", "both"):
        prepare_ieee_cis(cfg, args.nrows)
    if args.dataset in ("sparkov", "both"):
        prepare_sparkov(cfg, args.nrows)


if __name__ == "__main__":
    main()
