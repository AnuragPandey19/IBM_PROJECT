"""Build a transaction graph for the GraphSAGE Stage 2 specialist.

Design:
  - Node = transaction (one node per row)
  - Edge = two transactions share the same card1 (issuer/BIN identifier)
    We limit edges to each transaction's k most recent card1-siblings so the
    graph stays memory-friendly on a 6 GB GPU. k defaults to 5.
  - Node features = a subset of numeric features from Stage 1 (top-K by gain).
  - Node label = isFraud (used only for training nodes; val/test set masked).
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch_geometric.data import Data

log = logging.getLogger(__name__)


def build_transaction_graph(
    df: pd.DataFrame,
    feature_cols: list[str],
    k_neighbors: int = 5,
    entity_col: str = "card1",
    dt_col: str = "TransactionDT",
    label_col: str = "isFraud",
    scaler=None,
) -> Data:
    """Return a PyG Data object with x, edge_index, y for the given rows.

    scaler: optional pre-fitted StandardScaler. Neural nets need standardized
    input to train stably — the raw features mix tiny target_enc decimals
    (~0.03) with big counts (V317 in the thousands).
    """
    log.info("Building transaction graph: %d rows, %d features, k=%d",
             len(df), len(feature_cols), k_neighbors)

    X = df[feature_cols].fillna(0).astype("float32").values
    if scaler is not None:
        X = scaler.transform(X).astype("float32")
        log.info("Applied standardization (mean=%.3f, std=%.3f after)",
                 float(X.mean()), float(X.std()))
    y = df[label_col].astype("int64").values

    df_idx = df.reset_index(drop=True).copy()
    df_idx["_node_id"] = np.arange(len(df_idx), dtype=np.int64)
    df_idx_sorted = df_idx.sort_values([entity_col, dt_col], kind="mergesort")

    src_list, dst_list = [], []
    for _, group in df_idx_sorted.groupby(entity_col, sort=False):
        ids = group["_node_id"].values
        if len(ids) < 2:
            continue
        for i in range(1, len(ids)):
            lo = max(0, i - k_neighbors)
            for j in range(lo, i):
                src_list.append(ids[j])
                dst_list.append(ids[i])

    if len(src_list) == 0:
        log.warning("No edges built. Using self-loops.")
        src_list = list(range(len(df)))
        dst_list = list(range(len(df)))

    edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
    x = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.long)

    log.info("Graph built: %d nodes, %d edges (avg deg %.2f)",
             len(df), edge_index.shape[1], edge_index.shape[1] / len(df))

    return Data(x=x, edge_index=edge_index, y=y_tensor)


def pick_top_k_features(
    feature_importance_csv,
    k: int = 60,
    exclude_categoricals: list[str] = None,
) -> list[str]:
    """Pick the top K numeric features by Stage 1 gain importance."""
    from chimera_fd.features.engineering import LABEL_ENCODE_COLS
    exclude = set(exclude_categoricals or LABEL_ENCODE_COLS)

    imp = pd.read_csv(feature_importance_csv)
    imp_num = imp[~imp["feature"].isin(exclude)].reset_index(drop=True)
    top = imp_num.head(k)["feature"].tolist()
    log.info("Selected %d top-importance numeric features (excluded %d categoricals)",
             len(top), len(exclude))
    return top
