"""Tests for the ModelService — load, score, SHAP."""
from pathlib import Path

import pandas as pd
import pytest

from api.config import get_settings
from api.services.model_service import ModelService, get_model_service


settings = get_settings()


def _skip_if_no_model():
    if not settings.stage1_model_path.exists():
        pytest.skip("Stage 1 model file missing — run training first")


def test_singleton_returns_same_instance():
    a = get_model_service()
    b = get_model_service()
    assert a is b


def test_load_stage1_and_calibrator():
    _skip_if_no_model()
    ms = ModelService()
    ms.load()
    assert ms.loaded is True
    assert ms.stage1 is not None
    assert len(ms.feature_columns) > 0
    assert "isFraud" not in ms.feature_columns  # never a model input


def test_score_returns_expected_shape():
    _skip_if_no_model()
    ms = ModelService()
    ms.load()
    # Empty row — model should still return something
    X = pd.DataFrame([{c: 0.0 for c in ms.feature_columns}])
    result = ms.score(X)
    assert "raw_scores" in result
    assert "calibrated_scores" in result
    assert "decisions" in result
    assert "latency_ms" in result
    assert len(result["raw_scores"]) == 1
    assert len(result["decisions"]) == 1
    assert result["decisions"][0] in ("approve", "review", "block")
    assert result["latency_ms"] >= 0


def test_shap_returns_top_k_features():
    _skip_if_no_model()
    ms = ModelService()
    ms.load()
    X = pd.DataFrame([{c: 0.0 for c in ms.feature_columns}])
    explanations = ms.shap(X, top_k=5)
    assert len(explanations) == 1
    top = explanations[0]
    assert len(top) == 5
    for entry in top:
        assert "feature" in entry
        assert "value" in entry
        assert "contribution" in entry
        assert isinstance(entry["contribution"], float)


def test_missing_columns_filled_with_zero():
    _skip_if_no_model()
    ms = ModelService()
    ms.load()
    # Send only 2 columns — model expects hundreds
    X = pd.DataFrame([{"TransactionAmt": 100.0, "card1": 12345}])
    result = ms.score(X)
    assert len(result["raw_scores"]) == 1
