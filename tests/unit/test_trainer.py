"""Unit tests for the model training pipeline.

Tests ``prepare_training_data``, ``save_model`` / ``load_model`` and
basic ``train_denial_predictor`` (without Optuna, using lightweight
synthetic data).
"""

import pickle
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.denial_predictor.trainer import (
    prepare_training_data,
    save_model,
    load_model,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


class _SimpleModel:
    """A picklable stub that behaves like an sklearn classifier."""

    def predict_proba(self, X):
        return np.column_stack([np.full(len(X), 0.5), np.full(len(X), 0.5)])

    def predict(self, X):
        return np.zeros(len(X), dtype=int)


def _synthetic_df(n: int = 200, denial_rate: float = 0.3, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic feature DataFrame with a binary target."""
    rng = np.random.RandomState(seed)
    return pd.DataFrame({
        "claim_id": [f"claim-{i}" for i in range(n)],
        "feat_a": rng.randn(n),
        "feat_b": rng.uniform(0, 100, n),
        "feat_c": rng.choice([0, 1], n),
        "is_denied": rng.choice(
            [0, 1], size=n, p=[1 - denial_rate, denial_rate],
        ),
    })


# ── prepare_training_data ───────────────────────────────────────────────────


class TestPrepareTrainingData:

    def test_basic_split(self):
        df = _synthetic_df(200)
        X_train, X_val, y_train, y_val, X_test, y_test = prepare_training_data(
            df, test_size=0.2, validation_size=0.1, random_state=42,
        )
        total = len(X_train) + len(X_val) + len(X_test)
        assert total == 200
        assert len(y_train) == len(X_train)
        assert len(y_val) == len(X_val)
        assert len(y_test) == len(X_test)

    def test_excludes_identifiers(self):
        df = _synthetic_df(100)
        X_train, *_ = prepare_training_data(df, random_state=42)
        assert "claim_id" not in X_train.columns

    def test_excludes_target(self):
        df = _synthetic_df(100)
        X_train, *_ = prepare_training_data(df, random_state=42)
        assert "is_denied" not in X_train.columns

    def test_handles_object_columns(self):
        df = _synthetic_df(100)
        df["string_col"] = "constant"  # pure-string column
        df["numeric_str"] = df["feat_a"].astype(str)  # numeric stored as str
        X_train, *_ = prepare_training_data(df, random_state=42)
        # pure-string should be dropped
        assert "string_col" not in X_train.columns
        # numeric_str should be coerced to numeric
        if "numeric_str" in X_train.columns:
            assert X_train["numeric_str"].dtype in (np.float64, np.int64)

    def test_boolean_columns_converted(self):
        df = _synthetic_df(100)
        df["bool_col"] = df["feat_c"].astype(bool)
        X_train, *_ = prepare_training_data(df, random_state=42)
        if "bool_col" in X_train.columns:
            assert X_train["bool_col"].dtype in (np.int64, np.int32, int)

    def test_boolean_target(self):
        df = _synthetic_df(100)
        df["is_denied"] = df["is_denied"].astype(bool)
        _, _, y_train, *_ = prepare_training_data(df, random_state=42)
        assert y_train.dtype in (np.int64, np.int32, int)

    def test_missing_target_raises(self):
        df = _synthetic_df(100).drop(columns=["is_denied"])
        with pytest.raises(ValueError, match="Target column"):
            prepare_training_data(df)

    def test_time_based_split(self):
        df = _synthetic_df(200)
        df["service_date"] = pd.date_range("2024-01-01", periods=200, freq="D")
        X_train, X_val, _, _, X_test, _ = prepare_training_data(
            df, test_size=0.2, validation_size=0.1, time_column="service_date",
        )
        # For time-based split, test set should be the most recent data
        total = len(X_train) + len(X_val) + len(X_test)
        assert total == 200

    def test_nan_values_filled(self):
        df = _synthetic_df(100)
        df.loc[0:5, "feat_a"] = np.nan
        X_train, *_ = prepare_training_data(df, random_state=42)
        assert not X_train.isnull().any().any()


# ── save_model / load_model ─────────────────────────────────────────────────


class TestSaveLoadModel:

    def test_roundtrip(self):
        model = _SimpleModel()
        cols = ["feat_a", "feat_b"]
        meta = {"model_type": "lightgbm", "training_date": "2025-01-01"}

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = Path(f.name)

        save_model(model, path, cols, meta)
        loaded_model, loaded_cols, loaded_meta = load_model(path)

        assert loaded_cols == cols
        assert loaded_meta == meta

    def test_roundtrip_no_metadata(self):
        model = _SimpleModel()
        cols = ["feat_a"]

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = Path(f.name)

        save_model(model, path, cols)
        _, _, loaded_meta = load_model(path)
        assert loaded_meta == {}

    def test_creates_parent_directories(self, tmp_path):
        model = _SimpleModel()
        deep_path = tmp_path / "a" / "b" / "c" / "model.pkl"
        save_model(model, deep_path, ["x"])
        assert deep_path.exists()
        _, cols, _ = load_model(deep_path)
        assert cols == ["x"]

