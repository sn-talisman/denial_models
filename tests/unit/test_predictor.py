"""Unit tests for the DenialPredictor class."""

import pickle
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.models.denial_predictor.predictor import DenialPredictor


# ── Helpers ─────────────────────────────────────────────────────────────────


class _SimpleModel:
    """A picklable stub that behaves like an sklearn classifier."""

    def __init__(self, proba: np.ndarray | None = None, preds: np.ndarray | None = None):
        self._proba = proba if proba is not None else np.array([[0.7, 0.3]])
        self._preds = preds if preds is not None else np.array([0])

    def predict_proba(self, X):
        return self._proba

    def predict(self, X):
        return self._preds


def _make_mock_model(predict_proba_values=None, predict_values=None):
    """Create a MagicMock sklearn-like model (NOT picklable)."""
    model = MagicMock()
    if predict_proba_values is None:
        predict_proba_values = np.array([[0.7, 0.3]])
    if predict_values is None:
        predict_values = np.array([0])
    model.predict_proba = MagicMock(return_value=predict_proba_values)
    model.predict = MagicMock(return_value=predict_values)
    return model


def _save_model_to_file(model, feature_columns, metadata=None, path=None):
    """Serialize a model dict to a pickle file; return the path.

    ``model`` MUST be picklable (i.e. a ``_SimpleModel``, not a MagicMock).
    """
    data = {
        "model": model,
        "feature_columns": feature_columns,
        "metadata": metadata or {},
    }
    if path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".pkl", delete=False)
        path = tmp.name
        tmp.close()
    with open(path, "wb") as f:
        pickle.dump(data, f)
    return Path(path)


FEATURE_COLS = ["feat_a", "feat_b", "feat_c"]


# ── Initialization ──────────────────────────────────────────────────────────


class TestPredictorInit:
    """Tests for DenialPredictor.__init__."""

    def test_init_with_model_object(self):
        model = _make_mock_model()
        predictor = DenialPredictor(model=model, model_type="lightgbm")
        assert predictor.model is model
        assert predictor.model_type == "lightgbm"
        assert predictor.feature_columns is None

    def test_init_with_model_path(self):
        model = _SimpleModel()
        path = _save_model_to_file(model, FEATURE_COLS, {"model_type": "xgboost"})
        predictor = DenialPredictor(model_path=path)
        assert predictor.feature_columns == FEATURE_COLS
        assert predictor.model_type == "xgboost"

    def test_init_raises_without_model_or_path(self):
        with pytest.raises(ValueError, match="Either model_path or model must be provided"):
            DenialPredictor()

    def test_init_raises_for_missing_file(self):
        with pytest.raises(FileNotFoundError):
            DenialPredictor(model_path=Path("/nonexistent/model.pkl"))

    def test_model_type_auto_detect_lightgbm(self):
        model = _make_mock_model()
        model.__class__.__name__ = "LGBMClassifier"
        predictor = DenialPredictor(model=model)
        assert predictor.model_type == "lightgbm"

    def test_model_type_auto_detect_xgboost(self):
        model = _make_mock_model()
        model.__class__.__name__ = "XGBClassifier"
        predictor = DenialPredictor(model=model)
        assert predictor.model_type == "xgboost"

    def test_model_type_auto_detect_unknown(self):
        model = _make_mock_model()
        model.__class__.__name__ = "RandomForestClassifier"
        predictor = DenialPredictor(model=model)
        assert predictor.model_type == "unknown"

    def test_model_type_from_metadata(self):
        model = _SimpleModel()
        path = _save_model_to_file(model, FEATURE_COLS, {"model_type": "lightgbm"})
        predictor = DenialPredictor(model_path=path)
        assert predictor.model_type == "lightgbm"

    def test_explicit_model_type_takes_precedence(self):
        model = _SimpleModel()
        path = _save_model_to_file(model, FEATURE_COLS, {"model_type": "lightgbm"})
        predictor = DenialPredictor(model_path=path, model_type="xgboost")
        assert predictor.model_type == "xgboost"


# ── Single Prediction ───────────────────────────────────────────────────────


class TestPredict:
    """Tests for DenialPredictor.predict (single claim)."""

    def _predictor(self, proba_col1=0.3, feature_cols=None):
        """Helper to build a predictor with controlled probability output."""
        proba = np.array([[1 - proba_col1, proba_col1]])
        model = _make_mock_model(predict_proba_values=proba, predict_values=np.array([int(proba_col1 >= 0.5)]))
        return DenialPredictor(
            model=model,
            model_type="lightgbm",
        ), model

    def test_predict_returns_required_keys(self):
        predictor, _ = self._predictor(0.45)
        result = predictor.predict({"feat_a": 1, "feat_b": 2})
        assert "probability" in result
        assert "prediction" in result
        assert "risk_level" in result

    def test_predict_low_risk(self):
        predictor, _ = self._predictor(0.15)
        result = predictor.predict({"x": 1})
        assert result["risk_level"] == "low"
        assert result["probability"] == pytest.approx(0.15)

    def test_predict_medium_risk(self):
        predictor, _ = self._predictor(0.50)
        result = predictor.predict({"x": 1})
        assert result["risk_level"] == "medium"

    def test_predict_high_risk(self):
        predictor, _ = self._predictor(0.85)
        result = predictor.predict({"x": 1})
        assert result["risk_level"] == "high"

    def test_predict_from_series(self):
        predictor, _ = self._predictor(0.40)
        series = pd.Series({"feat_a": 1, "feat_b": 2})
        result = predictor.predict(series)
        assert result["probability"] == pytest.approx(0.40)

    def test_predict_from_dataframe(self):
        predictor, _ = self._predictor(0.60)
        df = pd.DataFrame([{"feat_a": 1, "feat_b": 2}])
        result = predictor.predict(df)
        assert result["probability"] == pytest.approx(0.60)

    def test_predict_fills_missing_features_with_zero(self):
        """When feature_columns are defined, missing columns are filled with 0."""
        proba = np.array([[0.5, 0.5]])
        model = _SimpleModel(proba=proba, preds=np.array([1]))
        path = _save_model_to_file(model, ["feat_a", "feat_b", "feat_c"])
        predictor = DenialPredictor(model_path=path)
        result = predictor.predict({"feat_a": 1.0})
        assert "probability" in result
        # Probability should come from our model
        assert result["probability"] == pytest.approx(0.5)

    def test_predict_fills_nan_with_zero(self):
        model = _make_mock_model(
            predict_proba_values=np.array([[0.6, 0.4]]),
            predict_values=np.array([0]),
        )
        predictor = DenialPredictor(model=model, model_type="lightgbm")
        result = predictor.predict({"feat_a": np.nan, "feat_b": 1})
        call_df = model.predict_proba.call_args[0][0]
        assert call_df.iloc[0]["feat_a"] == 0

    def test_predict_with_explanations_shap(self):
        """When return_explanations=True, SHAP path is attempted."""
        predictor, model = self._predictor(0.60)
        predictor.feature_columns = ["feat_a"]
        mock_explainer = MagicMock()
        mock_explainer.explain_prediction.return_value = {
            "feature_importance": {"feat_a": 0.4},
        }
        predictor._shap_explainer = mock_explainer

        result = predictor.predict({"feat_a": 1}, return_explanations=True)
        assert result["explanation_type"] == "SHAP"
        assert "feature_importance" in result

    def test_predict_explanations_fallback_to_feature_importances(self):
        """When SHAP fails, falls back to model feature_importances_."""
        proba = np.array([[0.3, 0.7]])
        model = _SimpleModel(proba=proba, preds=np.array([1]))
        model.feature_importances_ = np.array([0.6, 0.4])
        path = _save_model_to_file(model, ["feat_a", "feat_b"])
        predictor = DenialPredictor(model_path=path)
        # Force SHAP to fail
        predictor._shap_explainer = MagicMock()
        predictor._shap_explainer.explain_prediction.side_effect = RuntimeError("boom")

        result = predictor.predict({"feat_a": 1, "feat_b": 2}, return_explanations=True)
        assert result["explanation_type"] == "model_feature_importance"
        assert "feature_importance" in result
        assert result["feature_importance"]["feat_a"] == 0.6

    def test_predict_explanations_no_shap_no_importances(self):
        """When SHAP fails and model has no feature_importances_, result has no explanations."""
        predictor, model = self._predictor(0.40)
        del model.feature_importances_  # ensure attribute doesn't exist
        predictor._shap_explainer = MagicMock()
        predictor._shap_explainer.explain_prediction.side_effect = RuntimeError("boom")

        result = predictor.predict({"x": 1}, return_explanations=True)
        assert "feature_importance" not in result


# ── Batch Prediction ────────────────────────────────────────────────────────


class TestPredictBatch:
    """Tests for DenialPredictor.predict_batch."""

    def _batch_predictor(self, n=5):
        """Return a predictor wired with batch-sized mock outputs."""
        proba = np.column_stack([
            np.linspace(0.9, 0.1, n),
            np.linspace(0.1, 0.9, n),
        ])
        preds = (proba[:, 1] >= 0.5).astype(int)
        model = _make_mock_model(predict_proba_values=proba, predict_values=preds)
        return DenialPredictor(model=model, model_type="lightgbm"), model

    def test_batch_returns_dataframe(self):
        predictor, _ = self._batch_predictor(5)
        df = pd.DataFrame({"feat_a": range(5), "feat_b": range(5)})
        result = predictor.predict_batch(df)
        assert isinstance(result, pd.DataFrame)
        assert "denial_probability" in result.columns
        assert "denial_prediction" in result.columns
        assert "risk_level" in result.columns

    def test_batch_preserves_original_columns(self):
        predictor, _ = self._batch_predictor(3)
        df = pd.DataFrame({"feat_a": [1, 2, 3], "custom_col": ["a", "b", "c"]})
        result = predictor.predict_batch(df)
        assert "custom_col" in result.columns
        assert "feat_a" in result.columns

    def test_batch_correct_length(self):
        n = 10
        predictor, _ = self._batch_predictor(n)
        df = pd.DataFrame({"feat_a": range(n)})
        result = predictor.predict_batch(df)
        assert len(result) == n

    def test_batch_risk_levels_are_strings(self):
        predictor, _ = self._batch_predictor(5)
        df = pd.DataFrame({"feat_a": range(5)})
        result = predictor.predict_batch(df)
        # After .astype(str), values should be string-like
        assert all(isinstance(rl, str) for rl in result["risk_level"])
        assert all(rl in ("low", "medium", "high") for rl in result["risk_level"])

    def test_batch_fills_missing_features(self):
        """When feature_columns specified, missing columns are filled with 0."""
        n = 3
        proba = np.column_stack([np.full(n, 0.5), np.full(n, 0.5)])
        preds = np.zeros(n, dtype=int)
        model = _SimpleModel(proba=proba, preds=preds)
        path = _save_model_to_file(model, ["feat_a", "feat_b", "feat_c"])
        predictor = DenialPredictor(model_path=path)

        df = pd.DataFrame({"feat_a": [1, 2, 3]})
        result = predictor.predict_batch(df)
        assert len(result) == 3
        # All probabilities should be 0.5
        np.testing.assert_array_almost_equal(
            result["denial_probability"].values, [0.5, 0.5, 0.5],
        )

    def test_batch_nan_filled_with_zero(self):
        n = 2
        proba = np.column_stack([np.full(n, 0.6), np.full(n, 0.4)])
        preds = np.zeros(n, dtype=int)
        model = _make_mock_model(predict_proba_values=proba, predict_values=preds)
        predictor = DenialPredictor(model=model, model_type="xgboost")

        df = pd.DataFrame({"feat_a": [np.nan, 1.0], "feat_b": [2.0, np.nan]})
        predictor.predict_batch(df)
        call_X = model.predict_proba.call_args[0][0]
        assert call_X.iloc[0]["feat_a"] == 0
        assert call_X.iloc[1]["feat_b"] == 0

    def test_batch_probabilities_match_model(self):
        n = 4
        expected_probs = np.array([0.1, 0.4, 0.6, 0.9])
        proba = np.column_stack([1 - expected_probs, expected_probs])
        preds = (expected_probs >= 0.5).astype(int)
        model = _make_mock_model(predict_proba_values=proba, predict_values=preds)
        predictor = DenialPredictor(model=model, model_type="lightgbm")

        df = pd.DataFrame({"feat_a": range(n)})
        result = predictor.predict_batch(df)
        np.testing.assert_array_almost_equal(
            result["denial_probability"].values, expected_probs,
        )

    def test_batch_risk_level_boundaries(self):
        """Test risk level cut-off boundaries.

        pd.cut with bins=[0, 0.3, 0.7, 1.0] and include_lowest=True
        produces intervals: [-0.001, 0.3], (0.3, 0.7], (0.7, 1.0]
        So 0.30 → low, 0.31 → medium, 0.70 → medium, 0.71 → high.
        """
        probs = np.array([0.0, 0.29, 0.30, 0.31, 0.50, 0.69, 0.70, 0.71, 0.99])
        n = len(probs)
        proba = np.column_stack([1 - probs, probs])
        preds = (probs >= 0.5).astype(int)
        model = _make_mock_model(predict_proba_values=proba, predict_values=preds)
        predictor = DenialPredictor(model=model, model_type="lightgbm")

        df = pd.DataFrame({"feat_a": range(n)})
        result = predictor.predict_batch(df)
        levels = result["risk_level"].tolist()
        assert levels[0] == "low"     # 0.0
        assert levels[1] == "low"     # 0.29
        assert levels[2] == "low"     # 0.30  (boundary inclusive)
        assert levels[3] == "medium"  # 0.31
        assert levels[4] == "medium"  # 0.50
        assert levels[5] == "medium"  # 0.69
        assert levels[6] == "medium"  # 0.70  (boundary inclusive)
        assert levels[7] == "high"    # 0.71
        assert levels[8] == "high"    # 0.99


# ── Model Loading ───────────────────────────────────────────────────────────


class TestModelLoading:
    """Tests for _load_model / pickle round-trip."""

    def test_roundtrip_with_metadata(self):
        model = _SimpleModel()
        meta = {"model_type": "lightgbm", "training_date": "2025-06-01", "extra_key": 42}
        path = _save_model_to_file(model, FEATURE_COLS, meta)
        predictor = DenialPredictor(model_path=path)
        assert predictor.metadata["training_date"] == "2025-06-01"
        assert predictor.metadata["extra_key"] == 42

    def test_roundtrip_no_metadata(self):
        model = _SimpleModel()
        path = _save_model_to_file(model, FEATURE_COLS)
        predictor = DenialPredictor(model_path=path)
        assert predictor.metadata == {}

    def test_feature_columns_preserved(self):
        model = _SimpleModel()
        cols = ["alpha", "beta", "gamma", "delta"]
        path = _save_model_to_file(model, cols)
        predictor = DenialPredictor(model_path=path)
        assert predictor.feature_columns == cols
