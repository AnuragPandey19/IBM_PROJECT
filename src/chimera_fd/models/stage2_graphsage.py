"""Stage 2 - GraphSAGE specialist for uncertain transactions.

Architecture: 2-layer GraphSAGE (Hamilton et al. 2017) with hidden dim 128,
mean-aggregation, and a linear classification head. Trained with weighted BCE
loss - class weight equals scale_pos_weight from Stage 1 (~27), preserving
the CHIMERA-FD no-SMOTE principle.
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
from torch_geometric.nn import SAGEConv

log = logging.getLogger(__name__)


@dataclass
class GraphSAGEConfig:
    hidden_dim: int = 128
    num_layers: int = 2
    dropout: float = 0.3
    learning_rate: float = 5e-3
    weight_decay: float = 1e-5
    epochs: int = 30
    early_stopping_patience: int = 5
    batch_size: int = 4096
    num_neighbors: tuple = (25, 15)   # per-layer sampled neighbors


class GraphSAGE(nn.Module):
    """Two-layer GraphSAGE with dropout + BatchNorm."""

    def __init__(self, in_dim: int, hidden_dim: int = 128, num_layers: int = 2,
                 dropout: float = 0.3):
        super().__init__()
        self.num_layers = num_layers
        self.dropout = dropout

        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        dims = [in_dim] + [hidden_dim] * num_layers
        for i in range(num_layers):
            self.convs.append(SAGEConv(dims[i], dims[i + 1], aggr="mean"))
            self.norms.append(nn.BatchNorm1d(dims[i + 1]))

        # Classification head: hidden_dim -> 1 (logit)
        self.head = nn.Linear(hidden_dim, 1)

    def encode(self, x, edge_index):
        """Return node embeddings (hidden_dim) — for Fusion Head later."""
        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            x = conv(x, edge_index)
            x = norm(x)
            x = F.relu(x)
            if i < self.num_layers - 1:
                x = F.dropout(x, p=self.dropout, training=self.training)
        return x

    def forward(self, x, edge_index):
        """Return raw logits for classification."""
        z = self.encode(x, edge_index)
        return self.head(z).squeeze(-1)


class Stage2GraphSAGE:
    """Trainer + predictor + saver for GraphSAGE Stage 2."""

    def __init__(self, cfg: GraphSAGEConfig | None = None, device: str = "auto"):
        self.cfg = cfg or GraphSAGEConfig()
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        self.model: GraphSAGE | None = None
        self.in_dim: int = 0
        self.feature_names: list[str] = []

    def fit(self, train_data, val_data, feature_names: list[str], pos_weight: float):
        """Train GraphSAGE.

        Args:
            train_data, val_data: PyG Data objects
            feature_names: which columns of train_data.x correspond to what (for saving)
            pos_weight: weight of the positive class in BCE (= n_neg / n_pos on train)
        """
        from torch_geometric.loader import NeighborLoader

        self.feature_names = feature_names
        self.in_dim = train_data.x.shape[1]
        log.info("GraphSAGE: in_dim=%d, hidden=%d, layers=%d, device=%s",
                 self.in_dim, self.cfg.hidden_dim, self.cfg.num_layers, self.device)

        self.model = GraphSAGE(
            in_dim=self.in_dim,
            hidden_dim=self.cfg.hidden_dim,
            num_layers=self.cfg.num_layers,
            dropout=self.cfg.dropout,
        ).to(self.device)

        # NeighborLoader samples subgraphs for each mini-batch
        train_loader = NeighborLoader(
            train_data,
            num_neighbors=list(self.cfg.num_neighbors),
            batch_size=self.cfg.batch_size,
            shuffle=True,
            input_nodes=None,   # use all nodes as seeds
        )
        val_loader = NeighborLoader(
            val_data,
            num_neighbors=list(self.cfg.num_neighbors),
            batch_size=self.cfg.batch_size,
            shuffle=False,
        )

        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.cfg.learning_rate,
            weight_decay=self.cfg.weight_decay,
        )
        pos_weight_tensor = torch.tensor([pos_weight], device=self.device, dtype=torch.float32)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)

        best_val_ap = 0.0
        patience_left = self.cfg.early_stopping_patience
        history = []

        from sklearn.metrics import average_precision_score
        for epoch in range(1, self.cfg.epochs + 1):
            # ------ train ------
            self.model.train()
            train_loss = 0.0
            n_batches = 0
            for batch in train_loader:
                batch = batch.to(self.device)
                optimizer.zero_grad()
                logits = self.model(batch.x, batch.edge_index)
                # Only compute loss on the seed nodes (batch.batch_size)
                seed_logits = logits[:batch.batch_size]
                seed_y = batch.y[:batch.batch_size].float()
                loss = loss_fn(seed_logits, seed_y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
                n_batches += 1
            train_loss /= max(n_batches, 1)

            # ------ val ------
            self.model.eval()
            val_scores, val_y_all = [], []
            with torch.no_grad():
                for batch in val_loader:
                    batch = batch.to(self.device)
                    logits = self.model(batch.x, batch.edge_index)
                    seed_logits = logits[:batch.batch_size]
                    val_scores.append(torch.sigmoid(seed_logits).cpu().numpy())
                    val_y_all.append(batch.y[:batch.batch_size].cpu().numpy())
            val_scores = np.concatenate(val_scores)
            val_y_all = np.concatenate(val_y_all)
            val_ap = average_precision_score(val_y_all, val_scores)

            log.info("Epoch %2d: train_loss=%.4f  val_PR-AUC=%.4f",
                     epoch, train_loss, val_ap)
            history.append({"epoch": epoch, "train_loss": train_loss, "val_pr_auc": val_ap})

            if val_ap > best_val_ap + 1e-4:
                best_val_ap = val_ap
                patience_left = self.cfg.early_stopping_patience
                # Save best weights in memory
                self._best_state = {k: v.detach().clone() for k, v in self.model.state_dict().items()}
            else:
                patience_left -= 1
                if patience_left <= 0:
                    log.info("Early stopping at epoch %d (best val PR-AUC=%.4f)",
                             epoch, best_val_ap)
                    break

        # Restore best weights
        self.model.load_state_dict(self._best_state)
        self.history = history
        self.best_val_ap = best_val_ap
        return self

    def predict_proba(self, data, batch_size: int = 4096) -> np.ndarray:
        """Return P(fraud) per node."""
        from torch_geometric.loader import NeighborLoader
        self.model.eval()
        loader = NeighborLoader(
            data,
            num_neighbors=list(self.cfg.num_neighbors),
            batch_size=batch_size,
            shuffle=False,
        )
        probs = []
        with torch.no_grad():
            for batch in loader:
                batch = batch.to(self.device)
                logits = self.model(batch.x, batch.edge_index)
                seed_logits = logits[:batch.batch_size]
                probs.append(torch.sigmoid(seed_logits).cpu().numpy())
        return np.concatenate(probs)

    def get_embeddings(self, data, batch_size: int = 4096) -> np.ndarray:
        """Return hidden-dim embeddings for Fusion Head."""
        from torch_geometric.loader import NeighborLoader
        self.model.eval()
        loader = NeighborLoader(
            data,
            num_neighbors=list(self.cfg.num_neighbors),
            batch_size=batch_size,
            shuffle=False,
        )
        embs = []
        with torch.no_grad():
            for batch in loader:
                batch = batch.to(self.device)
                z = self.model.encode(batch.x, batch.edge_index)
                embs.append(z[:batch.batch_size].cpu().numpy())
        return np.concatenate(embs, axis=0)

    def save(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "state_dict": self.model.state_dict(),
            "cfg": self.cfg,
            "in_dim": self.in_dim,
            "feature_names": self.feature_names,
            "best_val_ap": self.best_val_ap,
        }, path)
        log.info("Saved Stage 2 model to %s", path)

    @classmethod
    def load(cls, path: str | Path, device: str = "auto") -> "Stage2GraphSAGE":
        payload = torch.load(path, map_location="cpu", weights_only=False)
        obj = cls(cfg=payload["cfg"], device=device)
        obj.in_dim = payload["in_dim"]
        obj.feature_names = payload["feature_names"]
        obj.model = GraphSAGE(
            in_dim=obj.in_dim,
            hidden_dim=obj.cfg.hidden_dim,
            num_layers=obj.cfg.num_layers,
            dropout=obj.cfg.dropout,
        ).to(obj.device)
        obj.model.load_state_dict(payload["state_dict"])
        obj.best_val_ap = payload.get("best_val_ap", 0.0)
        return obj
