"""Tests for the predictions API endpoints.

Uses httpx AsyncClient + ASGITransport to test the FastAPI app directly
without starting a real server.  The DenialPredictor is mocked through
FastAPI dependency overrides.
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.api.app import app
from src.api.routes.predictions import get_predictor


# ── Helpers ─────────────────────────────────────────────────────────────────


def _fake_predictor():
    """Return a MagicMock predictor with deterministic behaviour."""
    predictor = MagicMock()
    predictor.model_type = "lightgbm"
    predictor.feature_columns = ["feat_a", "feat_b"]
    predictor.metadata = {"training_date": "2025-06-01", "model_type": "lightgbm"}

    def _predict(features, return_explanations=False):
        result = {
            "probability": 0.75,
            "prediction": 1,
            "risk_level": "high",
        }
        if return_explanations:
            result["feature_importance"] = {"feat_a": 0.6, "feat_b": 0.4}
            result["explanation_type"] = "SHAP"
        return result

    predictor.predict = MagicMock(side_effect=_predict)

    def _predict_batch(features_df):
        n = len(features_df)
        result_df = features_df.copy()
        result_df["denial_probability"] = [0.75] * n
        result_df["denial_prediction"] = [1] * n
        result_df["risk_level"] = ["high"] * n
        return result_df

    predictor.predict_batch = MagicMock(side_effect=_predict_batch)
    return predictor


@pytest.fixture(autouse=True)
def _override_predictor():
    """Override the get_predictor dependency with our mock."""
    mock = _fake_predictor()
    app.dependency_overrides[get_predictor] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.fixture
def transport():
    return ASGITransport(app=app)


# ── POST /api/v1/predict ────────────────────────────────────────────────────


class TestPredictEndpoint:

    @pytest.mark.asyncio
    async def test_predict_success(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict", json={
                "claim_id": "c-1",
                "features": {"feat_a": 1.0, "feat_b": 0.5},
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["claim_id"] == "c-1"
        assert body["denial_probability"] == 0.75
        assert body["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_predict_missing_claim_id(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict", json={
                "features": {"feat_a": 1.0},
            })
        assert resp.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_predict_missing_features(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict", json={
                "claim_id": "c-1",
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_with_explanations(self, transport, _override_predictor):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict", json={
                "claim_id": "c-1",
                "features": {"feat_a": 1.0},
                "include_explanations": True,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("explanation_type") == "SHAP"
        assert "feature_importance" in body

    @pytest.mark.asyncio
    async def test_predict_internal_error(self, transport, _override_predictor):
        _override_predictor.predict.side_effect = RuntimeError("Model crash")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict", json={
                "claim_id": "c-1",
                "features": {"feat_a": 1.0},
            })
        assert resp.status_code == 500
        assert "Prediction failed" in resp.json()["detail"]


# ── POST /api/v1/predict/batch ──────────────────────────────────────────────


class TestBatchPredictEndpoint:

    @pytest.mark.asyncio
    async def test_batch_predict_success(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict/batch", json={
                "claims": [
                    {"claim_id": "c-1", "features": {"feat_a": 1.0}},
                    {"claim_id": "c-2", "features": {"feat_a": 2.0}},
                ],
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_processed"] == 2
        assert len(body["predictions"]) == 2
        assert body["predictions"][0]["claim_id"] == "c-1"

    @pytest.mark.asyncio
    async def test_batch_predict_empty_list(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict/batch", json={
                "claims": [],
            })
        assert resp.status_code == 200
        assert resp.json()["total_processed"] == 0

    @pytest.mark.asyncio
    async def test_batch_predict_exceeds_max(self, transport):
        claims = [{"claim_id": f"c-{i}", "features": {"a": i}} for i in range(1001)]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict/batch", json={
                "claims": claims,
                "max_claims": 10,
            })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_predict_internal_error(self, transport, _override_predictor):
        _override_predictor.predict_batch.side_effect = RuntimeError("boom")
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/predict/batch", json={
                "claims": [
                    {"claim_id": "c-1", "features": {"a": 1}},
                ],
            })
        assert resp.status_code == 500


# ── GET /api/v1/model/info ──────────────────────────────────────────────────


class TestModelInfoEndpoint:

    @pytest.mark.asyncio
    async def test_model_info_success(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/model/info")
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_type"] == "lightgbm"
        assert body["feature_count"] == 2
        assert body["feature_columns"] == ["feat_a", "feat_b"]
        assert body["training_date"] == "2025-06-01"

