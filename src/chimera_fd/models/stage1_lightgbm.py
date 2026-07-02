"""Stage 1: LightGBM Triage Scorer.

Handles class imbalance via `scale_pos_weight` (cost-sensitive) — NEVER SMOTE.
This choice is core to the CHIMERA-FD contribution: preserving the original
data distribution keeps downstream SHAP explanations faithful.
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from chimera_fd.features.engineering import LABEL_ENCODE_COLS

log = logging.getLogger(__name__)


@dataclass
class LightGBMConfig:
    num_boost_round: int = 2000
    early_stopping_rounds: int = 100
    scale_pos_weight: float | str = "auto"     # "auto" → n_neg / n_pos on train
    params: dict = None

    def default_params(self, scale_pos_weight_value: float) -> dict:
        base = {
            "objective": "binary",
            "metric": "average_precision",   # PR-AUC — the right primary metric
            "boosting_type": "gbdt",
            "learning_rate": 0.05,
            "num_leaves": 127,
            "max_depth": -1,
            "min_data_in_leaf": 100,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "lambda_l1": 0.1,
            "lambda_l2": 0.1,
            "scale_pos_weight": scale_pos_weight_value,
            "verbose": -1,
            "seed": 42,
        }
        if self.params:
            base.update(self.params)
        return base


class Stage1LightGBM:
    """LightGBM Stage 1 trainer, saver, and predictor."""

    def __init__(self, cfg: LightGBMConfig | None = None):
        self.cfg = cfg or LightGBMConfig()
        self.model: lgb.Booster | None = None
        self.feature_names: list[str] = []
        self.categorical_features: list[str] = []

    def _resolve_categorical(self, X: pd.DataFrame) -> list[str]:
        """Which columns in X are categoricals (from our label encoder)?"""
        return [c for c in LABEL_ENCODE_COLS if c in X.columns]

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_val: pd.DataFrame,
        y_val: np.ndarray,
    ) -> "Stage1LightGBM":
        self.feature_names = list(X_train.columns)
        self.categorical_features = self._resolve_categorical(X_train)

        # Compute scale_pos_weight from training set if 'auto'
        n_pos = int((y_train == 1).sum())
        n_neg = int((y_train == 0).sum())
        if self.cfg.scale_pos_weight == "auto":
            spw = n_neg / max(n_pos, 1)
        else:
            spw = float(self.cfg.scale_pos_weight)
        log.info("scale_pos_weight = %.2f (n_neg=%d / n_pos=%d)", spw, n_neg, n_pos)
        log.info("Categorical features: %d columns", len(self.categorical_features))

        params = self.cfg.default_params(spw)

        train_data = lgb.Dataset(
            X_train, label=y_train,
            categorical_feature=self.categorical_features,
            free_raw_data=False,
        )
        val_data = lgb.Dataset(
            X_val, label=y_val,
            categorical_feature=self.categorical_features,
            reference=train_data,
            free_raw_data=False,
        )

        log.info("Starting training. num_boost_round=%d, early_stopping=%d",
                 self.cfg.num_boost_round, self.cfg.early_stopping_rounds)

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.cfg.num_boost_round,
            valid_sets=[train_data, val_data],
            valid_names=["train", "val"],
            callbacks=[
                lgb.early_stopping(stopping_rounds=self.cfg.early_stopping_rounds),
                lgb.log_evaluation(period=100),
            ],
        )
        log.info("Training complete. Best iteration: %d", self.model.best_iteration)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model not fit. Call .fit() first.")
        # LightGBM returns probability of positive class directly
        return self.model.predict(X[self.feature_names], num_iteration=self.model.best_iteration)

    def feature_importance(self, importance_type: str = "gain") -> pd.DataFrame:
        if self.model is None:
            raise RuntimeError("Model not fit.")
        imp = self.model.feature_importance(importance_type=importance_type)
        return pd.DataFrame({
            "feature": self.feature_names,
            "importance": imp,
        }).sort_values("importance", ascending=False).reset_index(drop=True)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "feature_names": self.feature_names,
                "categorical_features": self.categorical_features,
                "config": self.cfg,
            }, f)
        log.info("Saved model to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "Stage1LightGBM":
        with open(path, "rb") as f:
            payload = pickle.load(f)
        obj = cls(cfg=payload["config"])
        obj.model = payload["model"]
        obj.feature_names = payload["feature_names"]
        obj.categorical_features = payload["categorical_features"]
        return obj
