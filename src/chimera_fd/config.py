"""Config loader. Reads config/config.yaml and resolves paths relative to project root."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Project root = directory containing config/. We resolve upward from this file.
# This file is src/chimera_fd/config.py  → root is three parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


class Config(dict):
    """Dict wrapper that supports attribute access: cfg.data.ieee_cis.train_transaction"""

    def __init__(self, data: dict):
        super().__init__(data)
        for k, v in data.items():
            if isinstance(v, dict):
                self[k] = Config(v)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e


def _resolve(path_str: str) -> Path:
    """Turn a possibly-relative path from config into an absolute Path.

    Rules:
    - Absolute paths (C:\\...) are returned as-is
    - Relative paths are resolved against PROJECT_ROOT
    """
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


def load_config(path: Path | str | None = None) -> Config:
    """Load config.yaml and return a Config object. Paths are pre-resolved."""
    if path is None:
        path = DEFAULT_CONFIG_PATH
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Resolve data paths
    for section in ("ieee_cis", "sparkov"):
        if section in raw.get("data", {}):
            for key, val in raw["data"][section].items():
                raw["data"][section][key] = str(_resolve(val))

    if "processed_dir" in raw.get("data", {}):
        raw["data"]["processed_dir"] = str(_resolve(raw["data"]["processed_dir"]))

    return Config(raw)


if __name__ == "__main__":
    # Quick sanity check
    cfg = load_config()
    print(f"Project root: {PROJECT_ROOT}")
    print(f"IEEE-CIS train_transaction: {cfg.data.ieee_cis.train_transaction}")
    print(f"Sparkov train: {cfg.data.sparkov.train}")
    print(f"Processed dir: {cfg.data.processed_dir}")
