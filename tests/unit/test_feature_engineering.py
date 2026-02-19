"""Unit tests for feature engineering modules."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from src.data_access.models import Claim, ClaimStatus, ClaimLineItem, DenialDetail
from src.pipelines.feature_engineering.claim_features import extract_claim_features
from src.pipelines.feature_engineering.cpt_carc_interactions import (
    extract_cpt_carc_interaction_features,
)
from src.pipelines.feature_engineering.rejection_patterns import (
    extract_rejection_pattern_features,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_claim(**kwargs) -> Claim:
    defaults = dict(
        claim_id="claim-1",
        practice_id="practice-1",
        payer_id="payer-1",
        status=ClaimStatus.PAID,
        total_billed_amount=Decimal("200.00"),
        service_date_from=date(2024, 6, 1),
        service_date_to=date(2024, 6, 1),
        submitted_date=date(2024, 6, 5),
    )
    defaults.update(kwargs)
    return Claim(**defaults)


def _make_line_item(**kwargs) -> ClaimLineItem:
    defaults = dict(
        line_item_id="li-1",
        claim_id="claim-1",
        line_number=1,
        cpt_code="HC:99213:25",
        billed_amount=Decimal("200.00"),
    )
    defaults.update(kwargs)
    return ClaimLineItem(**defaults)


def _make_denial(**kwargs) -> DenialDetail:
    defaults = dict(
        denial_id="d-1",
        claim_id="claim-1",
        carc_code=45,
        adjustment_amount=Decimal("200.00"),
    )
    defaults.update(kwargs)
    return DenialDetail(**defaults)


# ── Claim Features ──────────────────────────────────────────────────────────

class TestExtractClaimFeatures:
    """Tests for extract_claim_features."""

    def test_basic_features(self):
        claim = _make_claim()
        line_items = [_make_line_item()]
        features = extract_claim_features(claim, line_items)

        assert features["claim_id"] == "claim-1"
        assert features["total_billed_amount"] == 200.0
        assert features["line_item_count"] == 1

    def test_no_line_items(self):
        claim = _make_claim()
        features = extract_claim_features(claim, [])
        assert features["line_item_count"] == 0

    def test_multiple_line_items(self):
        claim = _make_claim()
        li1 = _make_line_item(line_item_id="li-1", cpt_code="HC:99213:25")
        li2 = _make_line_item(
            line_item_id="li-2",
            line_number=2,
            cpt_code="HC:97110:GN",
            billed_amount=Decimal("150.00"),
        )
        features = extract_claim_features(claim, [li1, li2])
        assert features["line_item_count"] == 2

    def test_denied_claim_status(self):
        claim = _make_claim(status=ClaimStatus.DENIED)
        features = extract_claim_features(claim, [_make_line_item()])
        assert "claim_status" in features

    def test_date_features(self):
        claim = _make_claim(
            service_date_from=date(2024, 6, 1),
            submitted_date=date(2024, 6, 5),
        )
        features = extract_claim_features(claim, [_make_line_item()])
        # Should have temporal features
        assert "service_date" in features or "submitted_date" in features


# ── CPT-CARC Interaction Features ───────────────────────────────────────────

class TestCPTCARCInteractions:
    """Tests for extract_cpt_carc_interaction_features."""

    def test_no_denial_details(self):
        claim = _make_claim()
        features = extract_cpt_carc_interaction_features(
            claim, [_make_line_item()], [], primary_cpt="99213",
        )
        assert isinstance(features, dict)
        assert features.get("primary_cpt_has_carc", 0) == 0

    def test_with_denial_details(self):
        claim = _make_claim(status=ClaimStatus.DENIED)
        li = _make_line_item(line_item_id="li-1")
        denial = _make_denial(line_item_id="li-1", carc_code=45, rarc_code="N130")
        features = extract_cpt_carc_interaction_features(
            claim, [li], [denial], primary_cpt="99213",
        )
        assert features.get("primary_cpt_has_carc", 0) == 1
        assert features.get("primary_cpt_carc_count", 0) >= 1

    def test_empty_line_items(self):
        claim = _make_claim()
        features = extract_cpt_carc_interaction_features(
            claim, [], [], primary_cpt="99213",
        )
        assert isinstance(features, dict)


# ── Rejection Pattern Features ──────────────────────────────────────────────

class TestRejectionPatterns:
    """Tests for extract_rejection_pattern_features."""

    def test_no_issues(self):
        claim = _make_claim(
            patient_id="patient-1",
            provider_id="provider-1",
        )
        features = extract_rejection_pattern_features(
            claim, [_make_line_item()], primary_cpt="99213",
        )
        assert isinstance(features, dict)
        # No missing fields → no rejection issues
        assert features.get("missing_patient_id", 0) == 0
        assert features.get("missing_provider_id", 0) == 0

    def test_missing_patient_id(self):
        claim = _make_claim(patient_id=None)
        features = extract_rejection_pattern_features(
            claim, [_make_line_item()], primary_cpt="99213",
        )
        assert features.get("missing_patient_id", 0) == 1

    def test_missing_provider_id(self):
        claim = _make_claim(provider_id=None)
        features = extract_rejection_pattern_features(
            claim, [_make_line_item()], primary_cpt="99213",
        )
        assert features.get("missing_provider_id", 0) == 1

    def test_missing_submitted_date(self):
        claim = _make_claim(submitted_date=None)
        features = extract_rejection_pattern_features(
            claim, [_make_line_item()], primary_cpt="99213",
        )
        assert features.get("missing_submitted_date", 0) == 1

    def test_invalid_date_order(self):
        # submitted_date before service_date is invalid
        claim = _make_claim(
            service_date_from=date(2024, 6, 10),
            submitted_date=date(2024, 6, 1),
        )
        features = extract_rejection_pattern_features(
            claim, [_make_line_item()], primary_cpt="99213",
        )
        assert features.get("invalid_date_order", 0) == 1

    def test_no_line_items(self):
        claim = _make_claim()
        features = extract_rejection_pattern_features(
            claim, [], primary_cpt="99213",
        )
        assert features.get("missing_line_items", 0) == 1

