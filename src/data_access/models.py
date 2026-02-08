"""Pydantic data models for claims, denials, and related entities.

These models represent the canonical data representation used throughout
the application. Both database and FHIR repositories must map their
source data into these models.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class ClaimStatus(str, Enum):
    """Claim status enumeration."""
    
    PENDING = "pending"
    SUBMITTED = "submitted"
    PAID = "paid"
    DENIED = "denied"
    REJECTED = "rejected"
    APPEALED = "appealed"
    VOIDED = "voided"


class Practice(BaseModel):
    """Medical practice/organization."""
    
    model_config = ConfigDict(frozen=True)
    
    practice_id: str = Field(..., description="Unique practice identifier")
    name: str = Field(..., description="Practice name")
    npi: Optional[str] = Field(None, description="National Provider Identifier")
    tax_id: Optional[str] = Field(None, description="Tax ID (redacted in logs)")
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class Payer(BaseModel):
    """Insurance payer/plan."""
    
    model_config = ConfigDict(frozen=True)
    
    payer_id: str = Field(..., description="Unique payer identifier")
    name: str = Field(..., description="Payer name")
    payer_type: Optional[str] = Field(None, description="Commercial, Medicare, Medicaid, etc.")
    plan_type: Optional[str] = Field(None, description="HMO, PPO, etc.")


class Patient(BaseModel):
    """Patient information (PHI - handle with care)."""
    
    model_config = ConfigDict(frozen=True)
    
    patient_id: str = Field(..., description="Unique patient identifier")
    date_of_birth: Optional[date] = Field(None, description="DOB (PHI)")
    gender: Optional[str] = None
    # Note: Name, SSN, etc. should NOT be stored in these models
    # Only use anonymized identifiers


class Provider(BaseModel):
    """Healthcare provider."""
    
    model_config = ConfigDict(frozen=True)
    
    provider_id: str = Field(..., description="Unique provider identifier")
    npi: Optional[str] = Field(None, description="National Provider Identifier")
    specialty: Optional[str] = Field(None, description="Provider specialty")
    name: Optional[str] = Field(None, description="Provider name (may be PHI)")


class ClaimLineItem(BaseModel):
    """Individual line item within a claim."""
    
    model_config = ConfigDict(frozen=True)
    
    line_item_id: str = Field(..., description="Unique line item identifier")
    claim_id: str = Field(..., description="Parent claim ID")
    line_number: int = Field(..., description="Line number within claim")
    cpt_code: Optional[str] = Field(None, description="CPT/HCPCS procedure code")
    modifiers: list[str] = Field(default_factory=list, description="Procedure modifiers")
    icd10_code: Optional[str] = Field(None, description="ICD-10 diagnosis code")
    units: Decimal = Field(default=Decimal("1.0"), description="Number of units")
    billed_amount: Decimal = Field(..., description="Billed amount for this line")
    place_of_service: Optional[str] = Field(None, description="Place of service code")
    service_date: Optional[date] = Field(None, description="Date of service")


class DenialDetail(BaseModel):
    """Denial or rejection reason detail."""
    
    model_config = ConfigDict(frozen=True)
    
    denial_id: str = Field(..., description="Unique denial detail identifier")
    claim_id: str = Field(..., description="Associated claim ID")
    line_item_id: Optional[str] = Field(None, description="Associated line item ID if line-specific")
    carc_code: Optional[int] = Field(None, description="Claim Adjustment Reason Code")
    rarc_code: Optional[str] = Field(None, description="Remittance Advice Remark Code")
    remark_code: Optional[str] = Field(None, description="Additional remark code")
    denial_reason_text: Optional[str] = Field(None, description="Free-text denial reason")
    denial_category: Optional[str] = Field(None, description="Normalized denial category")
    denial_date: Optional[date] = Field(None, description="Date of denial")
    adjustment_amount: Optional[Decimal] = Field(None, description="Adjustment amount")


class Claim(BaseModel):
    """Healthcare claim."""
    
    model_config = ConfigDict(frozen=True)
    
    claim_id: str = Field(..., description="Unique claim identifier")
    practice_id: str = Field(..., description="Practice ID")
    payer_id: str = Field(..., description="Payer ID")
    patient_id: Optional[str] = Field(None, description="Patient ID")
    provider_id: Optional[str] = Field(None, description="Billing provider ID")
    
    claim_number: Optional[str] = Field(None, description="External claim number")
    status: ClaimStatus = Field(..., description="Current claim status")
    
    service_date_from: Optional[date] = Field(None, description="Service date range start")
    service_date_to: Optional[date] = Field(None, description="Service date range end")
    submitted_date: Optional[date] = Field(None, description="Date claim was submitted")
    adjudicated_date: Optional[date] = Field(None, description="Date claim was adjudicated")
    
    total_billed_amount: Decimal = Field(..., description="Total billed amount")
    total_allowed_amount: Optional[Decimal] = Field(None, description="Total allowed amount")
    total_paid_amount: Optional[Decimal] = Field(None, description="Total paid amount")
    
    is_secondary_claim: bool = Field(default=False, description="Whether this is a secondary claim")
    has_prior_auth: bool = Field(default=False, description="Whether prior authorization was obtained")
    has_referral: bool = Field(default=False, description="Whether referral was obtained")
    
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Record update timestamp")


class DenialRateRecord(BaseModel):
    """Aggregated denial rate record for feature engineering."""
    
    model_config = ConfigDict(frozen=True)
    
    group_key: dict[str, str] = Field(..., description="Grouping dimensions (e.g., {'payer_id': 'X', 'cpt_code': 'Y'})")
    total_claims: int = Field(..., description="Total claims in group")
    denied_claims: int = Field(..., description="Number of denied claims")
    denial_rate: float = Field(..., description="Denial rate (0.0 to 1.0)")
    date_from: Optional[date] = Field(None, description="Start date of aggregation window")
    date_to: Optional[date] = Field(None, description="End date of aggregation window")

