"""Pydantic request/response schemas for API."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Request schema for denial prediction with pre-engineered features."""
    
    claim_id: str = Field(..., description="Unique claim identifier")
    features: Dict[str, Any] = Field(..., description="Pre-engineered feature dictionary")
    include_explanations: bool = Field(default=False, description="Include SHAP feature importance")


class ClaimDataRequest(BaseModel):
    """Request schema for denial prediction with raw claim data.
    
    This endpoint will perform feature engineering internally.
    """
    
    claim_id: str = Field(..., description="Unique claim identifier")
    # Core claim fields
    practice_id: str = Field(..., description="Practice ID")
    payer_id: str = Field(..., description="Payer ID")
    total_billed_amount: float = Field(..., description="Total billed amount")
    total_paid_amount: Optional[float] = Field(None, description="Total paid amount")
    total_allowed_amount: Optional[float] = Field(None, description="Total allowed amount")
    service_date: Optional[str] = Field(None, description="Service date (YYYY-MM-DD)")
    submitted_date: Optional[str] = Field(None, description="Submitted date (YYYY-MM-DD)")
    # Line items (simplified - can be expanded)
    line_items: Optional[list[Dict[str, Any]]] = Field(default=[], description="Claim line items")
    include_explanations: bool = Field(default=False, description="Include SHAP feature importance")


class PredictionResponse(BaseModel):
    """Response schema for denial prediction."""
    
    claim_id: str
    denial_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of denial (0.0 to 1.0)")
    denial_prediction: bool = Field(..., description="Binary prediction (True = denied, False = not denied)")
    risk_level: str = Field(..., description="Risk level: 'low', 'medium', or 'high'")
    feature_importance: Optional[Dict[str, float]] = Field(
        None, 
        description="Feature importance scores (if explanations requested)"
    )
    explanation_type: Optional[str] = Field(
        None,
        description="Type of explanation: 'SHAP' or 'model_feature_importance'"
    )


class BatchPredictionRequest(BaseModel):
    """Request schema for batch predictions."""
    
    claims: list[PredictionRequest] = Field(..., description="List of prediction requests")
    max_claims: int = Field(default=1000, le=1000, description="Maximum number of claims per batch")


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
