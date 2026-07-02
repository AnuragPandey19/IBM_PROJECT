"""Fusion Head — the multi-modal combiner.

Takes Stage 1 LightGBM predicted probability (a single number per transaction)
and Stage 2 GraphSAGE embedding (256-dim vector) and combines them via a small
MLP that outputs a final fraud probability.

This is the architectural primitive that no paper in our reviewed corpus
implements — every prior work is either full-tabular (LightGBM/XGBoost only)
or full-graph (GNN only). CHIMERA-FD's contribution is the concat + MLP.
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

log = logging.getLogger(__name__)


@dataclass
class FusionConfig:
    hidden_dim: int = 128
    dropout: float = 0.3
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    epochs: int = 40
    early_stopping_patience: int = 6
    batch_size: int = 2048


class FusionMLP(nn.Module):
    """Small feed-forward net that takes [stage1_prob, stage2_emb_256] -> logit."""

    def __init__(self, gnn_dim: int, hidden_dim: int = 128, dropout: float = 0.3):
        super().__init__()
        in_dim = gnn_dim + 1   # +1 for the Stage 1 probability
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, stage1_prob, gnn_emb):
        x = torch.cat([stage1_prob.unsqueeze(1), gnn_emb], dim=1)
        return self.net(x).squeeze(-1)


class FusionTrainer:
    """Trains + saves + loads the Fusion Head."""

    def __init__(self, cfg: FusionConfig | None = None, device: str = "auto"):
        self.cfg = cfg or FusionConfig()
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        self.model: FusionMLP | None = None
        self.gnn_dim: int = 0

    def fit(
        self,
        train_stage1: np.ndarray,
        train_gnn_emb: np.ndarray,
        train_y: np.ndarray,
        val_stage1: np.ndarray,
        val_gnn_emb: np.ndarray,
        val_y: np.ndarray,
        pos_weight: float,
    ):
        self.gnn_dim = train_gnn_emb.shape[1]
        log.info("Fusion Head: gnn_dim=%d, hidden=%d, device=%s",
                 self.gnn_dim, self.cfg.hidden_dim, self.device)

        self.model = FusionMLP(
            gnn_dim=self.gnn_dim,
            hidden_dim=self.cfg.hidden_dim,
            dropout=self.cfg.dropout,
        ).to(self.device)

        train_ds = TensorDataset(
            torch.tensor(train_stage1, dtype=torch.float32),
            torch.tensor(train_gnn_emb, dtype=torch.float32),
            torch.tensor(train_y, dtype=torch.float32),
        )
        train_loader = DataLoader(train_ds, batch_size=self.cfg.batch_size, shuffle=True)

        val_stage1_t = torch.tensor(val_stage1, dtype=torch.float32, device=self.device)
        val_gnn_t = torch.tensor(val_gnn_emb, dtype=torch.float32, device=self.device)

        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.cfg.learning_rate,
            weight_decay=self.cfg.weight_decay,
        )
        loss_fn = nn.BCEWithLogitsLoss(
            pos_weight=torch.tensor([pos_weight], device=self.device, dtype=torch.float32)
        )

        from sklearn.metrics import average_precision_score

        best_val_ap = 0.0
        patience_left = self.cfg.early_stopping_patience
        best_state = None

        for epoch in range(1, self.cfg.epochs + 1):
            self.model.train()
            train_loss = 0.0
            n_batches = 0
            for s1, gnn, y in train_loader:
                s1 = s1.to(self.device)
                gnn = gnn.to(self.device)
                y = y.to(self.device)
                optimizer.zero_grad()
                logits = self.model(s1, gnn)
                loss = loss_fn(logits, y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
                n_batches += 1
            train_loss /= max(n_batches, 1)

            self.model.eval()
            with torch.no_grad():
                val_logits = self.model(val_stage1_t, val_gnn_t)
                val_probs = torch.sigmoid(val_logits).cpu().numpy()
            val_ap = average_precision_score(val_y, val_probs)

            log.info("Epoch %2d: train_loss=%.4f  val_PR-AUC=%.4f",
                     epoch, train_loss, val_ap)

            if val_ap > best_val_ap + 1e-4:
                best_val_ap = val_ap
                patience_left = self.cfg.early_stopping_patience
                best_state = {k: v.detach().clone() for k, v in self.model.state_dict().items()}
            else:
                patience_left -= 1
                if patience_left <= 0:
                    log.info("Early stopping at epoch %d (best val PR-AUC=%.4f)",
                             epoch, best_val_ap)
                    break

        if best_state is not None:
            self.model.load_state_dict(best_state)
        self.best_val_ap = best_val_ap
        return self

    def predict_proba(self, stage1: np.ndarray, gnn_emb: np.ndarray) -> np.ndarray:
        self.model.eval()
        s1_t = torch.tensor(stage1, dtype=torch.float32, device=self.device)
        gnn_t = torch.tensor(gnn_emb, dtype=torch.float32, device=self.device)
        with torch.no_grad():
            logits = self.model(s1_t, gnn_t)
            return torch.sigmoid(logits).cpu().numpy()

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "state_dict": self.model.state_dict(),
            "cfg": self.cfg,
            "gnn_dim": self.gnn_dim,
            "best_val_ap": self.best_val_ap,
        }, path)
        log.info("Saved Fusion Head to %s", path)

    @classmethod
    def load(cls, path, device: str = "auto"):
        payload = torch.load(path, map_location="cpu", weights_only=False)
        obj = cls(cfg=payload["cfg"], device=device)
        obj.gnn_dim = payload["gnn_dim"]
        obj.model = FusionMLP(
            gnn_dim=obj.gnn_dim,
            hidden_dim=obj.cfg.hidden_dim,
            dropout=obj.cfg.dropout,
        ).to(obj.device)
        obj.model.load_state_dict(payload["state_dict"])
        obj.best_val_ap = payload.get("best_val_ap", 0.0)
        return obj
