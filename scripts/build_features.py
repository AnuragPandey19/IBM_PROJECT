"""Feature engineering CLI. Reads processed parquet → engineers features → saves.

Usage:
    python scripts/build_features.py
"""
from __future__ import annotations

import logging
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chimera_fd.config import load_config
from chimera_fd.data.loader import load_parquet
from chimera_fd.features.engineering import FeaturePipeline, get_feature_columns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_features")


def main():
    cfg = load_config()
    processed = Path(cfg.data.processed_dir) / "ieee_cis"

    if not (processed / "train.parquet").exists():
        raise SystemExit(
            f"Missing {processed / 'train.parquet'}. Run scripts/prepare_data.py first."
        )

    t0 = time.time()
    log.info("Loading splits...")
    train = load_parquet(processed / "train.parquet")
    val = load_parquet(processed / "val.parquet")
    test = load_parquet(processed / "test.parquet")

    log.info("Fitting feature pipeline on TRAIN only (avoids target leakage)...")
    pipe = FeaturePipeline()
    pipe.fit(train)

    log.info("=" * 50)
    log.info("Transforming TRAIN...")
    log.info("=" * 50)
    train_ft = pipe.transform(train)

    log.info("=" * 50)
    log.info("Transforming VAL...")
    log.info("=" * 50)
    val_ft = pipe.transform(val)

    log.info("=" * 50)
    log.info("Transforming TEST...")
    log.info("=" * 50)
    test_ft = pipe.transform(test)

    feat_cols = get_feature_columns(train_ft)
    log.info("Total feature columns (usable model inputs): %d", len(feat_cols))

    out_dir = processed
    log.info("Writing engineered parquet files to %s", out_dir)
    train_ft.to_parquet(out_dir / "train_features.parquet", index=False)
    val_ft.to_parquet(out_dir / "val_features.parquet", index=False)
    test_ft.to_parquet(out_dir / "test_features.parquet", index=False)

    # Save the fitted pipeline (for later inference)
    with open(out_dir / "feature_pipeline.pkl", "wb") as f:
        pickle.dump(pipe, f)
    log.info("Saved fitted pipeline: %s", out_dir / "feature_pipeline.pkl")

    # Save feature column list
    with open(out_dir / "feature_columns.txt", "w") as f:
        f.write("\n".join(feat_cols))
    log.info("Saved feature column list: %s", out_dir / "feature_columns.txt")

    log.info("=" * 50)
    log.info("Done in %.1f seconds.", time.time() - t0)
    log.info("Train features: %s", train_ft.shape)
    log.info("Val features:   %s", val_ft.shape)
    log.info("Test features:  %s", test_ft.shape)


if __name__ == "__main__":
    main()
