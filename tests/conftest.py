"""Shared fixtures for all test modules."""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from src.data_access.models import (
    Claim,
    ClaimStatus,
    Practice,
    Payer,
    ClaimLineItem,
    DenialDetail,
)


# ── Claim Factories ─────────────────────────────────────────────────────────

def _make_claim(
    claim_id: str = "claim-1",
    practice_id: str = "practice-1",
    payer_id: str = "payer-1",
    status: ClaimStatus = ClaimStatus.PAID,
    billed: float = 100.0,
    paid: float = 80.0,
    **kwargs,
) -> Claim:
    defaults = dict(
        claim_id=claim_id,
        practice_id=practice_id,
        payer_id=payer_id,
        patient_id=kwargs.pop("patient_id", "patient-1"),
        provider_id=kwargs.pop("provider_id", "provider-1"),
        status=status,
        total_billed_amount=Decimal(str(billed)),
        total_paid_amount=Decimal(str(paid)),
        service_date_from=kwargs.pop("service_date_from", date.today() - timedelta(days=30)),
        service_date_to=kwargs.pop("service_date_to", date.today() - timedelta(days=30)),
        submitted_date=kwargs.pop("submitted_date", date.today() - timedelta(days=25)),
    )
    defaults.update(kwargs)
    return Claim(**defaults)


@pytest.fixture
def sample_claims() -> list[Claim]:
    """A mix of paid, denied, and rejected claims."""
    return [
        _make_claim("c1", status=ClaimStatus.PAID, billed=200, paid=180),
        _make_claim("c2", status=ClaimStatus.DENIED, billed=300, paid=0),
        _make_claim("c3", status=ClaimStatus.PAID, billed=150, paid=120),
        _make_claim("c4", status=ClaimStatus.REJECTED, billed=250, paid=0),
        _make_claim("c5", status=ClaimStatus.PAID, billed=100, paid=90,
                     payer_id="payer-2"),
        _make_claim("c6", status=ClaimStatus.DENIED, billed=400, paid=0,
                     payer_id="payer-2"),
    ]


@pytest.fixture
def sample_practices() -> list[Practice]:
    return [
        Practice(practice_id="practice-1", name="Test Practice Alpha"),
        Practice(practice_id="practice-2", name="Test Practice Beta"),
    ]


@pytest.fixture
def sample_payers() -> list[Payer]:
    return [
        Payer(payer_id="payer-1", name="Aetna"),
        Payer(payer_id="payer-2", name="BlueCross"),
    ]


@pytest.fixture
def sample_line_items() -> list[ClaimLineItem]:
    return [
        ClaimLineItem(
            line_item_id="li-1",
            claim_id="c1",
            line_number=1,
            cpt_code="HC:99213:25",
            billed_amount=Decimal("200.00"),
        ),
        ClaimLineItem(
            line_item_id="li-2",
            claim_id="c2",
            line_number=1,
            cpt_code="HC:97110:GN",
            billed_amount=Decimal("300.00"),
        ),
    ]


@pytest.fixture
def sample_denial_details() -> list[DenialDetail]:
    return [
        DenialDetail(
            denial_id="d1",
            claim_id="c2",
            line_item_id="li-2",
            carc_code=45,
            rarc_code="N130",
            adjustment_amount=Decimal("300.00"),
        ),
        DenialDetail(
            denial_id="d2",
            claim_id="c6",
            carc_code=16,
            adjustment_amount=Decimal("400.00"),
        ),
    ]


# ── Prediction DataFrame ────────────────────────────────────────────────────

@pytest.fixture
def practice_predictions_df() -> pd.DataFrame:
    """DataFrame mimicking the output of ``get_practice_data``."""
    np.random.seed(42)
    n = 50
    is_denied = np.random.choice([True, False], size=n, p=[0.3, 0.7])
    probs = np.where(is_denied, np.random.uniform(0.6, 0.99, n), np.random.uniform(0.01, 0.4, n))
    risk = pd.cut(probs, bins=[0, 0.3, 0.7, 1.0], labels=["low", "medium", "high"])

    return pd.DataFrame({
        "claim_id": [f"claim-{i}" for i in range(n)],
        "practice_id": ["practice-1"] * n,
        "practice_name": ["Test Practice"] * n,
        "payer_id": np.random.choice(["payer-1", "payer-2"], n),
        "payer_name": np.random.choice(["Aetna", "BlueCross"], n),
        "is_denied": is_denied,
        "total_billed_amount": np.random.uniform(50, 500, n),
        "total_paid_amount": np.random.uniform(0, 400, n),
        "primary_cpt_code": np.random.choice(["99213", "97110", "92507", ""], n),
        "denial_probability": probs,
        "denial_prediction": is_denied,
        "risk_level": risk,
        "service_date": [date.today() - timedelta(days=i) for i in range(n)],
    })


# ── Mock Repository ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_repository(sample_claims, sample_practices, sample_payers, sample_line_items, sample_denial_details):
    """An AsyncMock repository wired with sample data."""
    repo = AsyncMock()
    repo.get_claims = AsyncMock(return_value=sample_claims)
    repo.get_practices = AsyncMock(return_value=sample_practices)
    repo.get_payers = AsyncMock(return_value=sample_payers)
    repo.get_claim_line_items = AsyncMock(return_value=sample_line_items)
    repo.get_denial_details = AsyncMock(return_value=sample_denial_details)
    repo.get_historical_denial_rates = AsyncMock(return_value=[])
    repo.close = AsyncMock()
    return repo


# ── Mock Predictor ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_predictor():
    """A MagicMock predictor that returns plausible predictions."""
    predictor = MagicMock()
    predictor.model_type = "lightgbm"
    predictor.feature_columns = ["feat_a", "feat_b"]
    predictor.metadata = {"training_date": "2025-01-01"}

    def _predict_batch(features_df):
        n = len(features_df)
        probs = np.random.uniform(0.05, 0.95, n)
        return pd.DataFrame({
            "denial_probability": probs,
            "denial_prediction": probs > 0.5,
            "risk_level": pd.cut(probs, bins=[0, 0.3, 0.7, 1.0], labels=["low", "medium", "high"]),
        })

    predictor.predict_batch = MagicMock(side_effect=_predict_batch)

    def _predict(features, return_explanations=False):
        prob = np.random.uniform(0.05, 0.95)
        return {
            "probability": prob,
            "prediction": prob > 0.5,
            "risk_level": "high" if prob > 0.7 else "medium" if prob > 0.3 else "low",
        }

    predictor.predict = MagicMock(side_effect=_predict)
    return predictor

