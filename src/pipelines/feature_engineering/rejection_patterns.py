"""Rejection pattern feature engineering.

Rejections happen BEFORE the claim is sent to the payer - they're caused by
missing or incorrect fields in the claim itself. This module creates features
that capture these patterns and their relationship to CPT codes.
"""

from typing import Optional
import structlog

from src.data_access.models import Claim, ClaimLineItem, ClaimStatus

logger = structlog.get_logger()


def extract_rejection_pattern_features(
    claim: Claim,
    line_items: list[ClaimLineItem],
    primary_cpt: Optional[str] = None,
) -> dict:
    """Extract features that indicate potential rejection patterns.
    
    Rejections are caused by missing or incorrect claim fields BEFORE
    the claim reaches the payer. This function identifies these issues
    and links them to specific CPT codes.
    
    Args:
        claim: Claim object
        line_items: List of line items for this claim
        primary_cpt: Primary CPT code (if already extracted)
        
    Returns:
        Dictionary of rejection pattern features
    """
    features = {}
    
    # Extract primary CPT if not provided
    if not primary_cpt and line_items:
        primary_cpt = line_items[0].cpt_code
        if primary_cpt and ":" in primary_cpt:
            parts = primary_cpt.split(":")
            primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
    
    # Check for missing required fields
    missing_patient_id = claim.patient_id is None or claim.patient_id == ""
    missing_provider_id = claim.provider_id is None or claim.provider_id == ""
    missing_claim_number = claim.claim_number is None or claim.claim_number == ""
    missing_service_date = claim.service_date_from is None
    missing_submitted_date = claim.submitted_date is None
    missing_payer_id = claim.payer_id is None or claim.payer_id == ""
    missing_practice_id = claim.practice_id is None or claim.practice_id == ""
    
    # Count missing fields
    missing_field_count = sum([
        missing_patient_id,
        missing_provider_id,
        missing_claim_number,
        missing_service_date,
        missing_submitted_date,
        missing_payer_id,
        missing_practice_id,
    ])
    
    features["missing_field_count"] = missing_field_count
    features["has_missing_fields"] = 1 if missing_field_count > 0 else 0
    features["missing_patient_id"] = 1 if missing_patient_id else 0
    features["missing_provider_id"] = 1 if missing_provider_id else 0
    features["missing_claim_number"] = 1 if missing_claim_number else 0
    features["missing_service_date"] = 1 if missing_service_date else 0
    features["missing_submitted_date"] = 1 if missing_submitted_date else 0
    
    # Check for invalid/incorrect data patterns
    # Invalid dates (submitted before service date)
    invalid_date_order = False
    if claim.service_date_from and claim.submitted_date:
        if claim.submitted_date < claim.service_date_from:
            invalid_date_order = True
    
    features["invalid_date_order"] = 1 if invalid_date_order else 0
    
    # Missing or empty line items
    missing_line_items = len(line_items) == 0
    features["missing_line_items"] = 1 if missing_line_items else 0
    
    # Invalid CPT codes in line items
    invalid_cpt_count = 0
    missing_cpt_in_line_items = 0
    for item in line_items:
        if not item.cpt_code or item.cpt_code == "":
            missing_cpt_in_line_items += 1
        else:
            # Check if CPT code looks invalid (too short, wrong format)
            cpt = item.cpt_code
            if ":" in cpt:
                parts = cpt.split(":")
                cpt = parts[1] if len(parts) > 1 else cpt
            # CPT codes are typically 5 digits
            if len(cpt) < 4 or not cpt[:4].isdigit():
                invalid_cpt_count += 1
    
    features["invalid_cpt_count"] = invalid_cpt_count
    features["missing_cpt_in_line_items"] = missing_cpt_in_line_items
    features["has_invalid_cpts"] = 1 if invalid_cpt_count > 0 else 0
    
    # Missing billed amounts
    missing_billed_amount = claim.total_billed_amount is None or float(claim.total_billed_amount) == 0
    features["missing_billed_amount"] = 1 if missing_billed_amount else 0
    
    # Check line item data quality
    line_items_with_missing_data = 0
    for item in line_items:
        if (not item.billed_amount or float(item.billed_amount) == 0 or
            not item.service_date):
            line_items_with_missing_data += 1
    
    features["line_items_with_missing_data"] = line_items_with_missing_data
    features["has_line_items_missing_data"] = 1 if line_items_with_missing_data > 0 else 0
    
    # Create CPT-specific rejection pattern features
    if primary_cpt:
        # Link missing fields to primary CPT
        if missing_patient_id:
            features[f"cpt_{primary_cpt}_missing_patient_id"] = 1
        if missing_provider_id:
            features[f"cpt_{primary_cpt}_missing_provider_id"] = 1
        if missing_service_date:
            features[f"cpt_{primary_cpt}_missing_service_date"] = 1
        if invalid_date_order:
            features[f"cpt_{primary_cpt}_invalid_date_order"] = 1
        if invalid_cpt_count > 0:
            features[f"cpt_{primary_cpt}_has_invalid_cpts"] = 1
        
        # Overall rejection risk for this CPT
        rejection_risk_score = (
            missing_field_count * 2 +  # Missing fields are critical
            invalid_date_order * 3 +    # Date issues are serious
            invalid_cpt_count * 2 +      # Invalid CPTs cause rejections
            missing_cpt_in_line_items * 2
        )
        features[f"cpt_{primary_cpt}_rejection_risk_score"] = rejection_risk_score
        features[f"cpt_{primary_cpt}_has_rejection_risk"] = 1 if rejection_risk_score > 0 else 0
    else:
        # No CPT code - this itself is a rejection risk
        features["missing_primary_cpt"] = 1
    
    # Overall claim completeness score
    completeness_score = 10 - min(missing_field_count * 2, 10)
    features["claim_completeness_score"] = completeness_score
    features["is_incomplete_claim"] = 1 if completeness_score < 7 else 0
    
    logger.debug("Extracted rejection pattern features",
                 primary_cpt=primary_cpt,
                 missing_fields=missing_field_count,
                 invalid_cpts=invalid_cpt_count,
                 feature_count=len(features))
    
    return features

