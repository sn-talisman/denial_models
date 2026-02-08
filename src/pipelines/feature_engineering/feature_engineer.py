"""Feature engineering orchestrator.

Combines all feature extraction modules to create a complete feature vector.
"""

from datetime import date
from typing import Optional
import pandas as pd
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.data_access.models import Claim, ClaimLineItem, ClaimStatus
from src.pipelines.feature_engineering.claim_features import (
    extract_claim_features,
    extract_cpt_features,
)
from src.pipelines.feature_engineering.temporal_features import (
    extract_temporal_features,
    extract_time_since_features,
)
from src.pipelines.feature_engineering.historical_features import (
    compute_historical_denial_rates,
)

logger = structlog.get_logger()


async def engineer_features(
    claim: Claim,
    line_items: list[ClaimLineItem],
    repository: ClaimsRepository,
    reference_date: Optional[date] = None,
) -> dict:
    """Engineer complete feature vector for a claim.
    
    Args:
        claim: Claim object
        line_items: List of line items for this claim
        repository: Claims repository for historical lookups
        reference_date: Reference date for temporal calculations
        
    Returns:
        Complete feature dictionary
    """
    if reference_date is None:
        reference_date = date.today()
    
    # 1. Extract claim-level features
    claim_features = extract_claim_features(claim, line_items)
    
    # 2. Extract CPT-specific features
    primary_cpt = claim_features.get("primary_cpt_code")
    if primary_cpt:
        cpt_features = extract_cpt_features(primary_cpt)
        claim_features.update(cpt_features)
    
    # 3. Extract temporal features
    service_date = claim_features.get("service_date")
    submitted_date = claim_features.get("submitted_date")
    temporal_features = extract_temporal_features(
        service_date=service_date,
        submitted_date=submitted_date,
        reference_date=reference_date,
    )
    claim_features.update(temporal_features)
    
    # 4. Check for denial details and adjustments
    # This includes:
    # - Full denials (claim not paid at all)
    # - Partial denials/adjustments (claim paid but less than billed, with CARC/RARC codes)
    # 
    # IMPORTANT: For fully paid claims (no adjustments), we don't count previous rejections
    # But for partially paid claims, we DO want to capture the CARC/RARC codes
    # because they explain why certain amounts weren't paid
    denial_details = await repository.get_denial_details(claim.claim_id)
    
    # Calculate adjustment amounts from denial details
    total_adjustment_from_details = 0.0
    carc_codes = []
    rarc_codes = []
    
    if denial_details:
        for detail in denial_details:
            if detail.adjustment_amount:
                total_adjustment_from_details += float(detail.adjustment_amount)
            if detail.carc_code:
                carc_codes.append(detail.carc_code)
            if detail.rarc_code:
                rarc_codes.append(detail.rarc_code)
    
    # Add adjustment features
    claim_features["denial_detail_count"] = len(denial_details)
    claim_features["has_adjustments"] = len(denial_details) > 0
    claim_features["unique_carc_count"] = len(set(carc_codes))
    claim_features["unique_rarc_count"] = len(set(rarc_codes))
    claim_features["total_adjustment_from_details"] = total_adjustment_from_details
    
    # Determine if claim is denied (full denial, not partial)
    # For partially paid claims, we want to capture the adjustments but not mark as "denied"
    # because the claim was still paid (just not fully)
    if denial_details:
        is_fully_paid = claim_features.get("payment_ratio", 0.0) >= 1.0
        is_partially_paid = claim_features.get("is_partially_paid", False)
        
        if claim.status != ClaimStatus.PAID:
            # Claim is not paid - could be denied or rejected
            if not claim_features.get("is_denied", False):
                # If we have denial details but status doesn't indicate denial, mark as denied
                # This catches cases where denial details exist but status field doesn't reflect it
                claim_features["is_denied"] = True
                logger.debug("Claim marked as denied based on denial details",
                            claim_id=claim.claim_id,
                            denial_count=len(denial_details),
                            current_status=claim.status.value if claim.status else None)
        elif is_partially_paid:
            # Claim is partially paid - capture adjustments but don't mark as "denied"
            # These are important for learning patterns about partial denials
            claim_features["has_partial_denial"] = True
            logger.debug("Claim is partially paid with adjustments",
                        claim_id=claim.claim_id,
                        adjustment_count=len(denial_details),
                        payment_ratio=claim_features.get("payment_ratio", 0.0),
                        carc_codes=list(set(carc_codes)),
                        rarc_codes=list(set(rarc_codes)))
        else:
            # Claim is fully paid - previous rejection/denial was fixed, don't count it
            # We don't have the original rejection context, so we can't learn from it
            logger.debug("Claim has denial details but is fully paid - ignoring (rejection was fixed)",
                        claim_id=claim.claim_id,
                        denial_count=len(denial_details))
    
    # 5. Extract historical denial rate features
    # This requires async repository calls
    historical_features = await compute_historical_denial_rates(
        repository=repository,
        payer_id=claim.payer_id,
        practice_id=claim.practice_id,
        cpt_code=primary_cpt,
        provider_id=claim.provider_id,
        window_days=365,
        reference_date=reference_date,
    )
    claim_features.update(historical_features)
    
    # 6. Time-since features (would require additional repository queries)
    # For now, we'll skip these as they need patient/practice history
    # Can be added later if needed
    
    logger.debug("Engineered features for claim",
                 claim_id=claim.claim_id,
                 total_features=len(claim_features),
                 has_historical=len(historical_features) > 0)
    
    return claim_features


async def engineer_features_batch(
    claims: list[Claim],
    repository: ClaimsRepository,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """Engineer features for a batch of claims.
    
    Args:
        claims: List of claim objects
        repository: Claims repository
        reference_date: Reference date for calculations
        
    Returns:
        DataFrame with one row per claim and features as columns
    """
    if reference_date is None:
        reference_date = date.today()
    
    feature_rows = []
    
    for claim in claims:
        try:
            # Get line items for this claim
            line_items = await repository.get_claim_line_items(claim.claim_id)
            
            # Engineer features
            features = await engineer_features(
                claim=claim,
                line_items=line_items,
                repository=repository,
                reference_date=reference_date,
            )
            
            # Add claim ID for reference
            features["claim_id"] = claim.claim_id
            
            feature_rows.append(features)
            
        except Exception as e:
            logger.error("Failed to engineer features for claim",
                        claim_id=claim.claim_id,
                        error=str(e))
            continue
    
    if not feature_rows:
        logger.warning("No features extracted from claims", claim_count=len(claims))
        return pd.DataFrame()
    
    df = pd.DataFrame(feature_rows)
    
    logger.info("Engineered features for claims",
                total_claims=len(claims),
                successful=len(feature_rows),
                feature_count=len(df.columns) if not df.empty else 0)
    
    return df

