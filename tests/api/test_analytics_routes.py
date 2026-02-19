"""Tests for the analytics API endpoints.

Mocks the underlying service functions so no real database or model
is required.  Tests use httpx AsyncClient + ASGITransport.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.api.app import app
from src.api.routes.predictions import get_predictor


# ── Shared helpers ──────────────────────────────────────────────────────────


def _fake_predictor():
    predictor = MagicMock()
    predictor.model_type = "lightgbm"
    predictor.feature_columns = ["feat_a"]
    predictor.metadata = {}
    predictor.predict_batch = MagicMock(side_effect=lambda df: _make_predictions_df(len(df)))
    return predictor


def _make_predictions_df(n: int = 10) -> pd.DataFrame:
    """Build a DataFrame that mirrors the output of get_practice_data."""
    np.random.seed(0)
    is_denied = np.random.choice([True, False], n, p=[0.3, 0.7])
    probs = np.where(is_denied, np.random.uniform(0.6, 0.95, n), np.random.uniform(0.05, 0.4, n))
    risk = pd.cut(probs, bins=[0, 0.3, 0.7, 1.0], labels=["low", "medium", "high"])

    return pd.DataFrame({
        "claim_id": [f"claim-{i}" for i in range(n)],
        "practice_id": ["p-1"] * n,
        "practice_name": ["Test Practice"] * n,
        "payer_id": np.random.choice(["pay-1", "pay-2"], n),
        "payer_name": np.random.choice(["Aetna", "BlueCross"], n),
        "is_denied": is_denied,
        "is_rejected": [False] * n,
        "total_billed_amount": np.random.uniform(50, 500, n),
        "total_paid_amount": np.random.uniform(0, 400, n),
        "primary_cpt_code": np.random.choice(["99213", "97110", "92507"], n),
        "denial_probability": probs,
        "denial_prediction": is_denied.astype(int),
        "risk_level": risk,
        "service_date": [date.today() - timedelta(days=i) for i in range(n)],
    })


@pytest.fixture(autouse=True)
def _override_predictor():
    mock = _fake_predictor()
    app.dependency_overrides[get_predictor] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.fixture
def transport():
    return ASGITransport(app=app)


PRACTICE_GUID = "p-1"


# ── Practice Performance Summary ────────────────────────────────────────────


class TestPerformanceSummary:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    async def test_performance_summary_success(
        self, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = _make_predictions_df(20)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/performance-summary",
                params={"days_back": 90},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["practice_id"] == PRACTICE_GUID
        assert "total_claims" in body
        assert "denial_rate" in body
        assert "recovery_potential" in body

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    async def test_performance_summary_no_claims(
        self, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = pd.DataFrame()

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/performance-summary",
            )
        assert resp.status_code == 404


# ── Action Items ────────────────────────────────────────────────────────────


class TestActionItems:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    @patch("src.api.routes.analytics_practice.get_carc_rarc_analysis")
    @patch("src.api.routes.analytics_practice.get_cpt_carc_correlation")
    async def test_action_items_success(
        self, mock_cpt_carc, mock_carc_rarc, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = _make_predictions_df(20)
        mock_carc_rarc.return_value = {"carc_codes": [], "rarc_codes": []}
        mock_cpt_carc.return_value = {"cpt_carc": [], "cpt_rarc": []}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/action-items",
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["practice_id"] == PRACTICE_GUID
        assert isinstance(body["action_items"], list)

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    @patch("src.api.routes.analytics_practice.get_carc_rarc_analysis")
    @patch("src.api.routes.analytics_practice.get_cpt_carc_correlation")
    async def test_action_items_empty(
        self, mock_cpt_carc, mock_carc_rarc, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = pd.DataFrame()
        mock_carc_rarc.return_value = {"carc_codes": [], "rarc_codes": []}
        mock_cpt_carc.return_value = {"cpt_carc": [], "cpt_rarc": []}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/action-items",
            )
        assert resp.status_code == 404


# ── Payer Performance ───────────────────────────────────────────────────────


class TestPayerPerformance:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    async def test_payer_performance_success(
        self, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = _make_predictions_df(20)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/payer-performance",
            )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["payers"], list)

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    async def test_payer_performance_no_claims(
        self, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = pd.DataFrame()

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/payer-performance",
            )
        assert resp.status_code == 404


# ── CPT Performance ─────────────────────────────────────────────────────────


class TestCPTPerformance:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    async def test_cpt_performance_success(
        self, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = _make_predictions_df(20)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/cpt-performance",
            )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["cpt_codes"], list)


# ── High-Risk Claims ────────────────────────────────────────────────────────


class TestHighRiskClaims:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_practice_data")
    async def test_high_risk_claims_success(
        self, mock_get_data, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_get_data.return_value = _make_predictions_df(20)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/high-risk-claims",
                params={"limit": 5},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["high_risk_claims"], list)
        assert len(body["high_risk_claims"]) <= 5


# ── Denial Reasons ──────────────────────────────────────────────────────────


class TestDenialReasons:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_carc_rarc_analysis")
    @patch("src.api.routes.analytics_practice._resolve_practice_name")
    async def test_denial_reasons_success(
        self, mock_name, mock_analysis, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_name.return_value = "Test Practice"
        mock_analysis.return_value = {
            "carc_codes": [{
                "carc_code": 45,
                "occurrence_count": 10,
                "affected_claims": 8,
                "total_adjustment_amount": 5000.0,
                "description": "Fee schedule",
            }],
            "rarc_codes": [{
                "rarc_code": "N130",
                "occurrence_count": 5,
                "affected_claims": 4,
                "total_adjustment_amount": 2000.0,
            }],
        }

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/denial-reasons",
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["carc_codes"]) == 1
        assert body["carc_codes"][0]["carc_code"] == 45


# ── CPT-CARC Correlation ───────────────────────────────────────────────────


class TestCPTCARCCorrelation:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_cpt_carc_correlation")
    @patch("src.api.routes.analytics_practice._resolve_practice_name")
    async def test_cpt_carc_success(
        self, mock_name, mock_corr, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_name.return_value = "Test Practice"
        mock_corr.return_value = {"cpt_carc": [], "cpt_rarc": []}

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/cpt-carc-correlation",
            )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["cpt_carc"], list)


# ── Rejection Patterns ──────────────────────────────────────────────────────


class TestRejectionPatterns:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_practice.get_repository")
    @patch("src.api.routes.analytics_practice.get_rejection_pattern_analysis")
    @patch("src.api.routes.analytics_practice._resolve_practice_name")
    async def test_rejection_patterns_success(
        self, mock_name, mock_analysis, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_name.return_value = "Test Practice"
        mock_analysis.return_value = {
            "rejection_patterns": [{
                "cpt_code": "99213",
                "total_rejections": 3,
                "total_claims": 50,
                "rejection_rate": 0.06,
                "missing_patient_id": 1,
                "missing_provider_id": 0,
                "missing_service_date": 0,
                "missing_submitted_date": 1,
                "invalid_date_order": 0,
                "missing_cpt_in_line_items": 0,
                "invalid_cpt_count": 0,
                "missing_billed_amount": 0,
                "missing_line_items": 0,
                "rejection_risk_score": 12,
            }],
        }

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/api/v1/analytics/practice/{PRACTICE_GUID}/rejection-patterns",
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["rejection_patterns"]) == 1
        assert body["rejection_patterns"][0]["cpt_code"] == "99213"


# ── Aggregate Endpoints ─────────────────────────────────────────────────────


class TestAggregateEndpoints:

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_aggregate.get_repository")
    @patch("src.api.routes.analytics_aggregate.run_aggregate_prediction_pipeline")
    async def test_practices_endpoint(
        self, mock_pipeline, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_pipeline.return_value = _make_predictions_df(30)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analytics/practices")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_aggregate.get_repository")
    @patch("src.api.routes.analytics_aggregate.run_aggregate_prediction_pipeline")
    async def test_practices_empty(
        self, mock_pipeline, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_pipeline.return_value = pd.DataFrame()

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analytics/practices")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    @patch("src.api.routes.analytics_aggregate.get_repository")
    @patch("src.api.routes.analytics_aggregate.run_aggregate_prediction_pipeline")
    async def test_payers_endpoint(
        self, mock_pipeline, mock_get_repo, transport,
    ):
        mock_repo = AsyncMock()
        mock_get_repo.return_value = mock_repo
        mock_pipeline.return_value = _make_predictions_df(30)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analytics/payers")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

