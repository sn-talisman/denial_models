"""Pydantic request/response schemas for all API endpoints.

Consolidated schema definitions for:
- Predictions (single & batch)
- Model info
- Aggregate analytics (practices, payers, combos)
- Practice-specific analytics (performance, action items, payer/CPT breakdowns)
- Denial reasons (CARC/RARC)
- CPT-CARC correlations
- Rejection patterns
- Overall insights
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


# ── Prediction Schemas ──────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    """Request schema for denial prediction with pre-engineered features."""
    claim_id: str = Field(..., description="Unique claim identifier")
    features: Dict[str, Any] = Field(..., description="Pre-engineered feature dictionary")
    include_explanations: bool = Field(default=False, description="Include SHAP feature importance")


class ClaimDataRequest(BaseModel):
    """Request schema for denial prediction with raw claim data."""
    claim_id: str = Field(..., description="Unique claim identifier")
    practice_id: str = Field(..., description="Practice ID")
    payer_id: str = Field(..., description="Payer ID")
    total_billed_amount: float = Field(..., description="Total billed amount")
    total_paid_amount: Optional[float] = Field(None, description="Total paid amount")
    total_allowed_amount: Optional[float] = Field(None, description="Total allowed amount")
    service_date: Optional[str] = Field(None, description="Service date (YYYY-MM-DD)")
    submitted_date: Optional[str] = Field(None, description="Submitted date (YYYY-MM-DD)")
    line_items: Optional[list[Dict[str, Any]]] = Field(default=[], description="Claim line items")
    include_explanations: bool = Field(default=False, description="Include SHAP feature importance")


class PredictionResponse(BaseModel):
    """Response schema for denial prediction."""
    claim_id: str
    denial_probability: float = Field(..., ge=0.0, le=1.0)
    denial_prediction: bool
    risk_level: str = Field(..., description="'low', 'medium', or 'high'")
    feature_importance: Optional[Dict[str, float]] = None
    explanation_type: Optional[str] = None


class BatchPredictionRequest(BaseModel):
    """Request schema for batch predictions."""
    claims: list[PredictionRequest]
    max_claims: int = Field(default=1000, le=1000)


class BatchPredictionResponse(BaseModel):
    """Response schema for batch predictions."""
    predictions: list[PredictionResponse]
    total_processed: int
    errors: Optional[list[Dict[str, Any]]] = None


class ModelInfoResponse(BaseModel):
    """Response schema for model information."""
    model_type: str
    feature_count: int
    feature_columns: list[str]
    training_date: Optional[str] = None
    train_size: Optional[int] = None
    validation_size: Optional[int] = None
    metrics: Optional[Dict[str, Any]] = None


# ── Aggregate Analytics Schemas ─────────────────────────────────────────────

class PracticeAnalysisResponse(BaseModel):
    """Practice-level analysis response."""
    practice_id: str
    practice_name: str
    total_claims: int
    denied_claims: int
    rejected_claims: int
    denied_or_rejected: int
    denial_rate: float
    rejection_rate: float
    denial_or_rejection_rate: float
    avg_denial_probability: float
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    high_risk_pct: float
    total_billed: float
    denied_billed: float
    denied_billed_pct: float


class PayerAnalysisResponse(BaseModel):
    """Payer-level analysis response."""
    payer_id: str
    payer_name: str
    total_claims: int
    denied_claims: int
    rejected_claims: int
    denied_or_rejected: int
    denial_rate: float
    rejection_rate: float
    denial_or_rejection_rate: float
    avg_denial_probability: float
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    high_risk_pct: float
    total_billed: float
    denied_billed: float
    denied_billed_pct: float


class PracticePayerComboResponse(BaseModel):
    """Practice-Payer combination analysis response."""
    practice_id: str
    practice_name: str
    payer_id: str
    payer_name: str
    total_claims: int
    denied_claims: int
    rejected_claims: int
    denied_or_rejected: int
    denial_rate: float
    rejection_rate: float
    denial_or_rejection_rate: float
    avg_denial_probability: float
    high_risk_count: int
    high_risk_pct: float
    total_billed: float
    denied_billed: float
    denied_billed_pct: float


# ── Practice-Specific Analytics Schemas ─────────────────────────────────────

class PerformanceInsights(BaseModel):
    """Performance insights sub-object."""
    trends: dict = {}
    comparisons: dict = {}
    key_issues: List[str] = []
    risk_factors: List[str] = []


class PerformanceSummaryResponse(BaseModel):
    """Performance summary for a single practice."""
    practice_id: str
    practice_name: str
    total_claims: int
    denied_claims: int
    denial_rate: float
    denial_rate_vs_overall: float
    total_billed: float
    total_paid: float
    denied_amount: float
    recovery_potential: float
    avg_denial_probability: float
    avg_probability_vs_overall: float
    high_risk_claims: int
    high_risk_pct: float
    insights: PerformanceInsights


class ActionItemResponse(BaseModel):
    """Single action item."""
    priority: str
    title: str
    financial_impact: float
    recommendation: str
    details: str
    type: str
    payer_name: Optional[str] = None
    cpt_code: Optional[str] = None
    carc_code: Optional[int] = None


class PrioritizedActionItemsResponse(BaseModel):
    """Prioritized action items for a practice."""
    practice_id: str
    practice_name: str
    action_items: List[ActionItemResponse]


class PayerPerformanceItem(BaseModel):
    """Single payer performance row."""
    payer_name: str
    total_claims: int
    denied_claims: int
    denial_rate: float
    total_billed: float
    total_paid: float
    denied_amount: float
    avg_denial_probability: float


class PayerPerformanceResponse(BaseModel):
    """Payer performance breakdown for a practice."""
    practice_id: str
    practice_name: str
    payers: List[PayerPerformanceItem]


class CPTPerformanceItem(BaseModel):
    """Single CPT code performance row."""
    cpt_code: str
    total_claims: int
    denied_claims: int
    denial_rate: float
    total_billed: float
    denied_amount: float
    avg_denial_probability: float


class CPTPerformanceResponse(BaseModel):
    """CPT code performance breakdown for a practice."""
    practice_id: str
    practice_name: str
    cpt_codes: List[CPTPerformanceItem]


class HighRiskClaimItem(BaseModel):
    """Single high-risk claim."""
    claim_id: Optional[str]
    payer_name: str
    cpt_code: Optional[str]
    denial_probability: float
    billed_amount: float
    is_denied: bool


class HighRiskClaimsResponse(BaseModel):
    """High-risk claims for a practice."""
    practice_id: str
    practice_name: str
    high_risk_claims: List[HighRiskClaimItem]


# ── Denial Reasons (CARC/RARC) Schemas ──────────────────────────────────────

class CARCCodeItem(BaseModel):
    """CARC code analysis item."""
    carc_code: int
    occurrence_count: int
    affected_claims: int
    total_adjustment_amount: float
    description: str


class RARCCodeItem(BaseModel):
    """RARC code analysis item."""
    rarc_code: str
    occurrence_count: int
    affected_claims: int
    total_adjustment_amount: float


class CARCRARCAnalysisResponse(BaseModel):
    """CARC/RARC analysis for a practice."""
    practice_id: str
    practice_name: str
    carc_codes: List[CARCCodeItem]
    rarc_codes: List[RARCCodeItem]


# ── CPT-CARC Correlation Schemas ────────────────────────────────────────────

class CPTCARCCorrelationItem(BaseModel):
    """CPT-CARC correlation item."""
    cpt_code: str
    carc_code: int
    occurrence_count: int
    affected_claims: int
    total_adjustment_amount: float
    carc_description: str


class CPTRARCCorrelationItem(BaseModel):
    """CPT-RARC correlation item."""
    cpt_code: str
    rarc_code: str
    occurrence_count: int
    affected_claims: int
    total_adjustment_amount: float


class CPTCARCCorrelationResponse(BaseModel):
    """CPT-CARC/RARC correlation analysis for a practice."""
    practice_id: str
    practice_name: str
    cpt_carc: List[CPTCARCCorrelationItem]
    cpt_rarc: List[CPTRARCCorrelationItem]


# ── Rejection Pattern Schemas ───────────────────────────────────────────────

class RejectionPatternItem(BaseModel):
    """Rejection pattern item by CPT code."""
    cpt_code: str
    total_rejections: int
    total_claims: int
    rejection_rate: float
    missing_patient_id: int
    missing_provider_id: int
    missing_service_date: int
    missing_submitted_date: int
    invalid_date_order: int
    missing_cpt_in_line_items: int
    invalid_cpt_count: int
    missing_billed_amount: int
    missing_line_items: int
    rejection_risk_score: int


class RejectionPatternResponse(BaseModel):
    """Rejection pattern analysis for a practice."""
    practice_id: str
    practice_name: str
    rejection_patterns: List[RejectionPatternItem]


# ── Overall Insights Schemas ────────────────────────────────────────────────

class OverallInsightsResponse(BaseModel):
    """Overall insights across all practices."""
    total_practices: int
    total_claims: int
    total_denials: int
    overall_denial_rate: float
    total_denied_amount: float
    top_carc_codes: List[dict]
    top_payers: List[dict]
    top_cpt_codes: List[dict]
    key_findings: List[str]
