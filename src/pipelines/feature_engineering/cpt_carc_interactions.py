"""CPT-CARC/RARC interaction feature engineering.

Creates features that capture the relationship between procedure codes (CPT)
and denial reason codes (CARC/RARC). This is critical for the model to learn
which procedure codes are associated with which denial reasons.
"""

from typing import Optional
from collections import defaultdict
import structlog

from src.data_access.models import Claim, ClaimLineItem, DenialDetail

logger = structlog.get_logger()


def extract_cpt_carc_interaction_features(
    claim: Claim,
    line_items: list[ClaimLineItem],
    denial_details: list[DenialDetail],
    primary_cpt: Optional[str] = None,
) -> dict:
    """Extract interaction features between CPT codes and CARC/RARC codes.
    
    This function creates features that help the model learn relationships like:
    - "CPT 97110 is often denied with CARC 45 (fee schedule)"
    - "CPT 97112 is often rejected with CARC 16 (missing information)"
    
    Handles both DENIALS and REJECTIONS separately, as they have different
    root causes and patterns.
    
    Args:
        claim: Claim object (contains status: DENIED, REJECTED, or PAID)
        line_items: List of line items for this claim
        denial_details: List of denial/rejection details (with CARC/RARC codes)
        primary_cpt: Primary CPT code (if already extracted)
        
    Returns:
        Dictionary of interaction features for both denials and rejections
    """
    features = {}
    
    # Extract primary CPT if not provided
    if not primary_cpt and line_items:
        primary_cpt = line_items[0].cpt_code
        if primary_cpt and ":" in primary_cpt:
            parts = primary_cpt.split(":")
            primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
    
    if not primary_cpt:
        # No CPT code available
        return features
    
    # Create a map of line_item_id -> CPT code
    line_item_cpt_map = {}
    for line_item in line_items:
        cpt_code = line_item.cpt_code
        if cpt_code and ":" in cpt_code:
            parts = cpt_code.split(":")
            cpt_code = parts[1] if len(parts) > 1 else cpt_code
        line_item_cpt_map[line_item.line_item_id] = cpt_code
    
    # Track CPT-CARC and CPT-RARC combinations for DENIALS only
    # Rejections don't have CARC/RARC codes - they're based on claim content issues
    cpt_carc_combinations = defaultdict(int)
    cpt_rarc_combinations = defaultdict(int)
    primary_cpt_carc_codes = set()
    primary_cpt_rarc_codes = set()
    
    # Only process denial details for DENIALS (not rejections)
    # Rejections are handled separately via rejection_pattern_features
    from src.data_access.models import ClaimStatus
    is_denial = (claim.status == ClaimStatus.DENIED)
    is_partial_denial = (
        claim.status == ClaimStatus.PAID and
        claim.total_paid_amount and
        claim.total_billed_amount and
        float(claim.total_paid_amount) < float(claim.total_billed_amount)
    )
    
    # Only process CARC/RARC codes for denials (not rejections)
    # Rejections don't reach the payer, so they don't have CARC/RARC codes
    if is_denial or is_partial_denial:
        # Match denial details to line items (and thus CPT codes)
        for detail in denial_details:
            # Find the CPT code for this denial detail
            cpt_code = None
            
            # Try to match by line_item_id first
            if detail.line_item_id:
                cpt_code = line_item_cpt_map.get(detail.line_item_id)
            
            # If no match, use primary CPT (denial might be claim-level)
            if not cpt_code:
                cpt_code = primary_cpt
            
            if not cpt_code:
                continue
            
            # Track CARC codes
            if detail.carc_code:
                key = (cpt_code, detail.carc_code)
                cpt_carc_combinations[key] += 1
                
                # If this matches the primary CPT, track it
                if cpt_code == primary_cpt:
                    primary_cpt_carc_codes.add(detail.carc_code)
            
            # Track RARC codes
            if detail.rarc_code:
                key = (cpt_code, detail.rarc_code)
                cpt_rarc_combinations[key] += 1
                
                # If this matches the primary CPT, track it
                if cpt_code == primary_cpt:
                    primary_cpt_rarc_codes.add(detail.rarc_code)
    
    # Create features for primary CPT with common CARC codes
    # These are the most important relationships
    common_carc_codes = [1, 2, 3, 4, 5, 6, 16, 18, 22, 27, 29, 45, 50, 95]
    for carc_code in common_carc_codes:
        feature_name = f"has_cpt_{primary_cpt}_carc_{carc_code}"
        features[feature_name] = 1 if carc_code in primary_cpt_carc_codes else 0
    
    # Count features
    features["primary_cpt_carc_count"] = len(primary_cpt_carc_codes)
    features["primary_cpt_rarc_count"] = len(primary_cpt_rarc_codes)
    features["total_cpt_carc_combinations"] = len(cpt_carc_combinations)
    features["total_cpt_rarc_combinations"] = len(cpt_rarc_combinations)
    
    # Most common CARC code for primary CPT (if any)
    if primary_cpt_carc_codes:
        # Use the most frequent one
        primary_cpt_carc_freq = {}
        for detail in denial_details:
            if detail.carc_code and detail.carc_code in primary_cpt_carc_codes:
                # Check if this detail is for the primary CPT
                detail_cpt = None
                if detail.line_item_id:
                    detail_cpt = line_item_cpt_map.get(detail.line_item_id)
                if not detail_cpt:
                    detail_cpt = primary_cpt
                
                if detail_cpt == primary_cpt:
                    carc = detail.carc_code
                    primary_cpt_carc_freq[carc] = primary_cpt_carc_freq.get(carc, 0) + 1
        
        if primary_cpt_carc_freq:
            most_common_carc = max(primary_cpt_carc_freq.items(), key=lambda x: x[1])[0]
            features["primary_cpt_most_common_carc"] = most_common_carc
        else:
            features["primary_cpt_most_common_carc"] = 0
    else:
        features["primary_cpt_most_common_carc"] = 0
    
    # Binary indicator: Does primary CPT have any CARC codes?
    features["primary_cpt_has_carc"] = 1 if primary_cpt_carc_codes else 0
    features["primary_cpt_has_rarc"] = 1 if primary_cpt_rarc_codes else 0
    
    logger.debug("Extracted CPT-CARC interaction features",
                 primary_cpt=primary_cpt,
                 carc_count=len(primary_cpt_carc_codes),
                 rarc_count=len(primary_cpt_rarc_codes),
                 feature_count=len(features))
    
    return features


def extract_cpt_carc_historical_features(
    primary_cpt: Optional[str],
    historical_cpt_carc_rates: Optional[dict] = None,
) -> dict:
    """Extract historical features for CPT-CARC combinations.
    
    These features are used during prediction to leverage historical patterns.
    For example: "Historically, CPT 97110 with CARC 45 has a 80% denial rate"
    
    Args:
        primary_cpt: Primary CPT code
        historical_cpt_carc_rates: Dictionary mapping (cpt, carc) -> denial_rate
        
    Returns:
        Dictionary of historical interaction features
    """
    features = {}
    
    if not primary_cpt or not historical_cpt_carc_rates:
        return features
    
    # Common CARC codes to track
    common_carc_codes = [1, 2, 3, 4, 5, 6, 16, 18, 22, 27, 29, 45, 50, 95]
    
    for carc_code in common_carc_codes:
        key = (primary_cpt, carc_code)
        if key in historical_cpt_carc_rates:
            rate = historical_cpt_carc_rates[key]
            feature_name = f"hist_denial_rate_cpt_{primary_cpt}_carc_{carc_code}"
            features[feature_name] = rate
        else:
            feature_name = f"hist_denial_rate_cpt_{primary_cpt}_carc_{carc_code}"
            features[feature_name] = 0.0
    
    return features

