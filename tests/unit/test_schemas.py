"""Unit tests for API Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.api.schemas import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    ModelInfoResponse,
    PracticeAnalysisResponse,
    PayerAnalysisResponse,
    PracticePayerComboResponse,
    PerformanceInsights,
    PerformanceSummaryResponse,
    ActionItemResponse,
    PrioritizedActionItemsResponse,
    PayerPerformanceItem,
    PayerPerformanceResponse,
    CPTPerformanceItem,
    CPTPerformanceResponse,
    HighRiskClaimItem,
    HighRiskClaimsResponse,
    CARCCodeItem,
    RARCCodeItem,
    CARCRARCAnalysisResponse,
    CPTCARCCorrelationItem,
    CPTRARCCorrelationItem,
    CPTCARCCorrelationResponse,
    RejectionPatternItem,
    RejectionPatternResponse,
    OverallInsightsResponse,
)


class TestPredictionSchemas:
    """Test prediction request/response schemas."""

    def test_prediction_request_valid(self):
        req = PredictionRequest(
            claim_id="c-1",
            features={"feat_a": 1.0, "feat_b": 0.5},
        )
        assert req.claim_id == "c-1"
        assert req.include_explanations is False

    def test_prediction_request_missing_claim_id(self):
        with pytest.raises(ValidationError):
            PredictionRequest(features={"a": 1})

    def test_prediction_response_valid(self):
        resp = PredictionResponse(
            claim_id="c-1",
            denial_probability=0.85,
            denial_prediction=True,
            risk_level="high",
        )
        assert resp.denial_probability == 0.85
        assert resp.feature_importance is None

    def test_prediction_response_probability_bounds(self):
        with pytest.raises(ValidationError):
            PredictionResponse(
                claim_id="c-1",
                denial_probability=1.5,
                denial_prediction=True,
                risk_level="high",
            )

    def test_batch_prediction_request(self):
        req = BatchPredictionRequest(
            claims=[
                PredictionRequest(claim_id="c-1", features={"a": 1}),
                PredictionRequest(claim_id="c-2", features={"a": 2}),
            ]
        )
        assert len(req.claims) == 2
        assert req.max_claims == 1000

    def test_model_info_response(self):
        resp = ModelInfoResponse(
            model_type="lightgbm",
            feature_count=100,
            feature_columns=["a", "b"],
        )
        assert resp.model_type == "lightgbm"
        assert resp.training_date is None


class TestAggregateAnalyticsSchemas:
    """Test aggregate-level analytics schemas."""

    def test_practice_analysis_response(self):
        r = PracticeAnalysisResponse(
            practice_id="p-1",
            practice_name="Test",
            total_claims=100,
            denied_claims=20,
            rejected_claims=5,
            denied_or_rejected=25,
            denial_rate=0.20,
            rejection_rate=0.05,
            denial_or_rejection_rate=0.25,
            avg_denial_probability=0.15,
            high_risk_count=10,
            medium_risk_count=30,
            low_risk_count=60,
            high_risk_pct=0.10,
            total_billed=50000.0,
            denied_billed=10000.0,
            denied_billed_pct=0.20,
        )
        assert r.total_claims == 100

    def test_payer_analysis_response(self):
        r = PayerAnalysisResponse(
            payer_id="pay-1",
            payer_name="Aetna",
            total_claims=50,
            denied_claims=10,
            rejected_claims=2,
            denied_or_rejected=12,
            denial_rate=0.20,
            rejection_rate=0.04,
            denial_or_rejection_rate=0.24,
            avg_denial_probability=0.12,
            high_risk_count=5,
            medium_risk_count=15,
            low_risk_count=30,
            high_risk_pct=0.10,
            total_billed=25000.0,
            denied_billed=5000.0,
            denied_billed_pct=0.20,
        )
        assert r.payer_name == "Aetna"

    def test_practice_payer_combo_response(self):
        r = PracticePayerComboResponse(
            practice_id="p-1",
            practice_name="Test",
            payer_id="pay-1",
            payer_name="Aetna",
            total_claims=30,
            denied_claims=6,
            rejected_claims=1,
            denied_or_rejected=7,
            denial_rate=0.20,
            rejection_rate=0.033,
            denial_or_rejection_rate=0.233,
            avg_denial_probability=0.15,
            high_risk_count=3,
            high_risk_pct=0.10,
            total_billed=15000.0,
            denied_billed=3000.0,
            denied_billed_pct=0.20,
        )
        assert r.practice_id == "p-1"


class TestPracticeAnalyticsSchemas:
    """Test practice-specific analytics schemas."""

    def test_performance_insights_defaults(self):
        pi = PerformanceInsights()
        assert pi.trends == {}
        assert pi.key_issues == []

    def test_performance_summary_response(self):
        r = PerformanceSummaryResponse(
            practice_id="p-1",
            practice_name="Test",
            total_claims=200,
            denied_claims=40,
            denial_rate=0.20,
            denial_rate_vs_overall=-0.04,
            total_billed=100000.0,
            total_paid=80000.0,
            denied_amount=20000.0,
            recovery_potential=6000.0,
            avg_denial_probability=0.18,
            avg_probability_vs_overall=0.08,
            high_risk_claims=15,
            high_risk_pct=0.075,
            insights=PerformanceInsights(key_issues=["High denial rate"]),
        )
        assert r.recovery_potential == 6000.0

    def test_action_item_response(self):
        r = ActionItemResponse(
            priority="HIGH",
            title="Review payer denials",
            financial_impact=10000.0,
            recommendation="Renegotiate rates",
            details="50% denial rate",
            type="payer",
            payer_name="Aetna",
        )
        assert r.cpt_code is None
        assert r.carc_code is None

    def test_prioritized_action_items_response(self):
        r = PrioritizedActionItemsResponse(
            practice_id="p-1",
            practice_name="Test",
            action_items=[
                ActionItemResponse(
                    priority="HIGH",
                    title="Item 1",
                    financial_impact=5000,
                    recommendation="Fix it",
                    details="Details",
                    type="payer",
                ),
            ],
        )
        assert len(r.action_items) == 1

    def test_payer_performance_item(self):
        item = PayerPerformanceItem(
            payer_name="Aetna",
            total_claims=50,
            denied_claims=10,
            denial_rate=0.20,
            total_billed=25000.0,
            total_paid=20000.0,
            denied_amount=5000.0,
            avg_denial_probability=0.15,
        )
        assert item.payer_name == "Aetna"

    def test_cpt_performance_item(self):
        item = CPTPerformanceItem(
            cpt_code="99213",
            total_claims=40,
            denied_claims=8,
            denial_rate=0.20,
            total_billed=20000.0,
            denied_amount=4000.0,
            avg_denial_probability=0.18,
        )
        assert item.cpt_code == "99213"

    def test_high_risk_claim_item(self):
        item = HighRiskClaimItem(
            claim_id="c-1",
            payer_name="Aetna",
            cpt_code="99213",
            denial_probability=0.92,
            billed_amount=300.0,
            is_denied=True,
        )
        assert item.denial_probability == 0.92

    def test_high_risk_claims_response(self):
        r = HighRiskClaimsResponse(
            practice_id="p-1",
            practice_name="Test",
            high_risk_claims=[],
        )
        assert len(r.high_risk_claims) == 0


class TestDenialReasonsSchemas:
    """Test CARC/RARC denial reason schemas."""

    def test_carc_code_item(self):
        item = CARCCodeItem(
            carc_code=45,
            occurrence_count=10,
            affected_claims=8,
            total_adjustment_amount=5000.0,
            description="Charges exceed fee schedule",
        )
        assert item.carc_code == 45

    def test_rarc_code_item(self):
        item = RARCCodeItem(
            rarc_code="N130",
            occurrence_count=5,
            affected_claims=4,
            total_adjustment_amount=2000.0,
        )
        assert item.rarc_code == "N130"

    def test_carc_rarc_analysis_response(self):
        r = CARCRARCAnalysisResponse(
            practice_id="p-1",
            practice_name="Test",
            carc_codes=[],
            rarc_codes=[],
        )
        assert len(r.carc_codes) == 0


class TestCPTCARCCorrelationSchemas:
    """Test CPT-CARC correlation schemas."""

    def test_cpt_carc_correlation_item(self):
        item = CPTCARCCorrelationItem(
            cpt_code="97110",
            carc_code=45,
            occurrence_count=6,
            affected_claims=5,
            total_adjustment_amount=3000.0,
            carc_description="Charges exceed fee schedule",
        )
        assert item.cpt_code == "97110"

    def test_cpt_rarc_correlation_item(self):
        item = CPTRARCCorrelationItem(
            cpt_code="97110",
            rarc_code="N130",
            occurrence_count=3,
            affected_claims=3,
            total_adjustment_amount=1500.0,
        )
        assert item.rarc_code == "N130"

    def test_cpt_carc_correlation_response(self):
        r = CPTCARCCorrelationResponse(
            practice_id="p-1",
            practice_name="Test",
            cpt_carc=[],
            cpt_rarc=[],
        )
        assert len(r.cpt_carc) == 0


class TestRejectionPatternSchemas:
    """Test rejection pattern schemas."""

    def test_rejection_pattern_item(self):
        item = RejectionPatternItem(
            cpt_code="99213",
            total_rejections=5,
            total_claims=50,
            rejection_rate=0.10,
            missing_patient_id=1,
            missing_provider_id=0,
            missing_service_date=0,
            missing_submitted_date=2,
            invalid_date_order=0,
            missing_cpt_in_line_items=0,
            invalid_cpt_count=0,
            missing_billed_amount=0,
            missing_line_items=1,
            rejection_risk_score=17,
        )
        assert item.rejection_risk_score == 17

    def test_rejection_pattern_response(self):
        r = RejectionPatternResponse(
            practice_id="p-1",
            practice_name="Test",
            rejection_patterns=[],
        )
        assert len(r.rejection_patterns) == 0


class TestOverallInsightsSchema:
    """Test overall insights schema."""

    def test_overall_insights_response(self):
        r = OverallInsightsResponse(
            total_practices=10,
            total_claims=5000,
            total_denials=1000,
            overall_denial_rate=0.20,
            total_denied_amount=500000.0,
            top_carc_codes=[],
            top_payers=[],
            top_cpt_codes=[],
            key_findings=["High denial rate"],
        )
        assert r.total_practices == 10
        assert len(r.key_findings) == 1

