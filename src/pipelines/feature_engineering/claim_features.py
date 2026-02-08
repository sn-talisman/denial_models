"""Claim-level feature extraction.

Extracts features directly from claim and line item data.
"""

from decimal import Decimal
from typing import Optional
from datetime import date, datetime
import structlog

from src.data_access.models import Claim, ClaimLineItem

logger = structlog.get_logger()


def extract_claim_features(claim: Claim, line_items: list[ClaimLineItem]) -> dict:
    """Extract claim-level features from claim and line items.
    
    Args:
        claim: Claim object
        line_items: List of line items for this claim
        
    Returns:
        Dictionary of claim-level features
    """
    from src.data_access.models import ClaimStatus
    
    features = {}
    
    # Basic claim identifiers
    features["claim_id"] = claim.claim_id
    features["claim_number"] = claim.claim_number
    
    # Dates
    features["service_date"] = claim.service_date_from
    features["submitted_date"] = claim.submitted_date
    features["adjudicated_date"] = claim.adjudicated_date
    
    # Amounts
    features["total_billed_amount"] = float(claim.total_billed_amount or 0)
    features["total_paid_amount"] = float(claim.total_allowed_amount or 0) if claim.total_allowed_amount else 0.0
    features["total_allowed_amount"] = float(claim.total_allowed_amount or 0) if claim.total_allowed_amount else 0.0
    
    # Calculate payment ratio
    if features["total_billed_amount"] > 0:
        features["payment_ratio"] = features["total_paid_amount"] / features["total_billed_amount"]
    else:
        features["payment_ratio"] = 0.0
    
    # Partially paid claim detection
    # A claim is partially paid if it has a payment but less than billed amount
    # This is important because insurance provides CARC/RARC codes explaining adjustments
    features["is_partially_paid"] = (
        features["total_paid_amount"] > 0 
        and features["total_billed_amount"] > 0 
        and features["payment_ratio"] < 1.0
    )
    
    # Adjustment amount (difference between billed and paid)
    features["adjustment_amount"] = features["total_billed_amount"] - features["total_paid_amount"]
    
    # Adjustment ratio (what percentage was adjusted/denied)
    if features["total_billed_amount"] > 0:
        features["adjustment_ratio"] = features["adjustment_amount"] / features["total_billed_amount"]
    else:
        features["adjustment_ratio"] = 0.0
    
    # Line item counts and aggregations
    features["line_item_count"] = len(line_items)
    
    # Initialize aggregations
    total_line_billed = 0.0
    total_line_units = 0.0
    
    if line_items:
        # Primary CPT code (first line item's CPT)
        primary_cpt = line_items[0].cpt_code
        if primary_cpt and ":" in primary_cpt:
            # Handle format like "HC:92507:GN" - extract middle part
            parts = primary_cpt.split(":")
            primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
        features["primary_cpt_code"] = primary_cpt
        
        # Aggregate line item amounts
        total_line_billed = sum(float(item.billed_amount or 0) for item in line_items)
        total_line_units = sum(float(item.units or 0) for item in line_items)
        features["total_line_billed"] = total_line_billed
        features["total_line_units"] = total_line_units
        
        # Modifiers
        all_modifiers = []
        for item in line_items:
            if item.modifiers:
                all_modifiers.extend(item.modifiers)
        features["modifier_count"] = len(all_modifiers)
        features["has_modifiers"] = len(all_modifiers) > 0
        
        # Unique modifiers
        unique_modifiers = set(all_modifiers)
        features["unique_modifier_count"] = len(unique_modifiers)
    else:
        features["primary_cpt_code"] = None
        features["total_line_billed"] = 0.0
        features["total_line_units"] = 0.0
        features["modifier_count"] = 0
        features["has_modifiers"] = False
        features["unique_modifier_count"] = 0
    
    
    # CPT code diversity (number of unique CPT codes)
    unique_cpts = set()
    for item in line_items:
        if item.cpt_code:
            cpt = item.cpt_code
            if ":" in cpt:
                cpt = cpt.split(":")[1] if len(cpt.split(":")) > 1 else cpt
            unique_cpts.add(cpt)
    features["unique_cpt_count"] = len(unique_cpts)
    features["has_multiple_cpts"] = len(unique_cpts) > 1
    
    # Amount per unit
    if total_line_units > 0:
        features["amount_per_unit"] = features["total_billed_amount"] / total_line_units
    else:
        features["amount_per_unit"] = features["total_billed_amount"]
    
    # Status (will be used as target for training)
    features["claim_status"] = claim.status.value if claim.status else "pending"
    
    # IMPORTANT: Denials vs Rejections
    # - DENIED: Final state - claim was adjudicated and denied (clinical/business logic)
    # - REJECTED: Temporary state - claim was rejected before acceptance (technical/administrative)
    #   CRITICAL: Only count rejections if claim is STILL rejected (not subsequently paid/denied)
    #   If a claim was rejected then fixed and paid/denied, we don't have the original rejection info
    #   and shouldn't count it as a negative outcome since it was eventually resolved
    
    # is_denied: Only true if claim is currently DENIED (not rejected)
    # Denials are final outcomes - if a claim is denied, it stays denied
    features["is_denied"] = (claim.status == ClaimStatus.DENIED) if claim.status else False
    
    # is_rejected: Only true if claim is currently REJECTED (still in rejected state)
    # This captures claims that are still in rejected state and haven't been fixed yet
    # If a claim was rejected but is now paid/denied, we don't count the rejection
    # because we don't have the original rejection context
    features["is_rejected"] = (claim.status == ClaimStatus.REJECTED) if claim.status else False
    
    # Note: We'll check denial details separately in the feature engineering orchestrator
    # to catch denials that may not be reflected in status
    # But we'll exclude claims that are currently PAID (previous rejection was fixed)
    
    logger.debug("Extracted claim features", 
                 claim_id=claim.claim_id,
                 feature_count=len(features),
                 primary_cpt=features.get("primary_cpt_code"))
    
    return features


def extract_cpt_features(cpt_code: Optional[str]) -> dict:
    """Extract features from CPT code.
    
    Args:
        cpt_code: CPT code string (may include prefixes like "HC:92507:GN")
        
    Returns:
        Dictionary of CPT-related features
    """
    features = {}
    
    if not cpt_code:
        features["cpt_code"] = None
        features["cpt_category"] = None
        features["cpt_is_numeric"] = False
        return features
    
    # Extract numeric part
    if ":" in cpt_code:
        parts = cpt_code.split(":")
        numeric_cpt = parts[1] if len(parts) > 1 else cpt_code
    else:
        numeric_cpt = cpt_code
    
    features["cpt_code"] = numeric_cpt
    
    # Check if numeric
    try:
        int(numeric_cpt)
        features["cpt_is_numeric"] = True
    except ValueError:
        features["cpt_is_numeric"] = False
    
    # CPT category (rough categorization by code range)
    if numeric_cpt and numeric_cpt.isdigit():
        cpt_num = int(numeric_cpt)
        if 10000 <= cpt_num <= 69999:
            features["cpt_category"] = "surgery"
        elif 70000 <= cpt_num <= 79999:
            features["cpt_category"] = "radiology"
        elif 80000 <= cpt_num <= 89999:
            features["cpt_category"] = "pathology"
        elif 90000 <= cpt_num <= 99999:
            features["cpt_category"] = "medicine"
        else:
            features["cpt_category"] = "other"
    else:
        features["cpt_category"] = "hcpcs"  # HCPCS codes (alphanumeric)
    
    return features
