"""Historical denial rate feature engineering.

Computes historical denial rates and aggregates for feature engineering.
"""

from datetime import date, timedelta
from typing import Optional
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.data_access.models import DenialRateRecord

logger = structlog.get_logger()


async def compute_historical_denial_rates(
    repository: ClaimsRepository,
    payer_id: Optional[str] = None,
    practice_id: Optional[str] = None,
    cpt_code: Optional[str] = None,
    provider_id: Optional[str] = None,
    window_days: int = 365,
    reference_date: Optional[date] = None,
) -> dict:
    """Compute historical denial rates for feature engineering.
    
    Args:
        repository: Claims repository instance
        payer_id: Payer ID to filter by
        practice_id: Practice ID to filter by
        cpt_code: CPT code to filter by
        provider_id: Provider ID to filter by
        window_days: Time window in days (default 365)
        reference_date: Reference date for window (defaults to today)
        
    Returns:
        Dictionary with denial rate features:
        - hist_denial_rate_cpt_payer: Denial rate for CPT-payer combination
        - hist_denial_rate_practice: Practice-level denial rate
        - hist_denial_rate_provider: Provider-level denial rate
        - hist_denial_count_cpt_payer_90d: Denial count in last 90 days
        - hist_denial_count_cpt_payer_180d: Denial count in last 180 days
        - hist_denial_count_cpt_payer_365d: Denial count in last 365 days
    """
    features = {}
    
    if reference_date is None:
        reference_date = date.today()
    
    date_from = reference_date - timedelta(days=window_days)
    
    # Compute denial rates by different groupings
    # 1. CPT-Payer combination
    if cpt_code and payer_id:
        records = await repository.get_historical_denial_rates(
            group_by=["cpt_code", "payer_id"],
            date_from=date_from,
            date_to=reference_date,
        )
        
        # Find matching record
        matching_record = None
        for record in records:
            if (record.group_key.get("cpt_code") == cpt_code and 
                record.group_key.get("payer_id") == payer_id):
                matching_record = record
                break
        
        if matching_record:
            features["hist_denial_rate_cpt_payer"] = matching_record.denial_rate
            features["hist_denial_count_cpt_payer"] = matching_record.denied_claims
            features["hist_total_claims_cpt_payer"] = matching_record.total_claims
        else:
            features["hist_denial_rate_cpt_payer"] = 0.0
            features["hist_denial_count_cpt_payer"] = 0
            features["hist_total_claims_cpt_payer"] = 0
    
    # 2. Practice-level
    if practice_id:
        records = await repository.get_historical_denial_rates(
            group_by=["practice_id"],
            date_from=date_from,
            date_to=reference_date,
        )
        
        matching_record = None
        for record in records:
            if record.group_key.get("practice_id") == practice_id:
                matching_record = record
                break
        
        if matching_record:
            features["hist_denial_rate_practice"] = matching_record.denial_rate
            features["hist_denial_count_practice"] = matching_record.denied_claims
            features["hist_total_claims_practice"] = matching_record.total_claims
        else:
            features["hist_denial_rate_practice"] = 0.0
            features["hist_denial_count_practice"] = 0
            features["hist_total_claims_practice"] = 0
    
    # 3. Provider-level
    if provider_id:
        records = await repository.get_historical_denial_rates(
            group_by=["provider_id"],
            date_from=date_from,
            date_to=reference_date,
        )
        
        matching_record = None
        for record in records:
            if record.group_key.get("provider_id") == provider_id:
                matching_record = record
                break
        
        if matching_record:
            features["hist_denial_rate_provider"] = matching_record.denial_rate
            features["hist_denial_count_provider"] = matching_record.denied_claims
            features["hist_total_claims_provider"] = matching_record.total_claims
        else:
            features["hist_denial_rate_provider"] = 0.0
            features["hist_denial_count_provider"] = 0
            features["hist_total_claims_provider"] = 0
    
    # 4. Time-windowed counts (90d, 180d, 365d)
    if cpt_code and payer_id:
        for window in [90, 180, 365]:
            window_date_from = reference_date - timedelta(days=window)
            records = await repository.get_historical_denial_rates(
                group_by=["cpt_code", "payer_id"],
                date_from=window_date_from,
                date_to=reference_date,
            )
            
            matching_record = None
            for record in records:
                if (record.group_key.get("cpt_code") == cpt_code and 
                    record.group_key.get("payer_id") == payer_id):
                    matching_record = record
                    break
            
            if matching_record:
                features[f"hist_denial_count_cpt_payer_{window}d"] = matching_record.denied_claims
                features[f"hist_total_claims_cpt_payer_{window}d"] = matching_record.total_claims
            else:
                features[f"hist_denial_count_cpt_payer_{window}d"] = 0
                features[f"hist_total_claims_cpt_payer_{window}d"] = 0
    
    logger.debug("Computed historical features",
                 payer_id=payer_id,
                 practice_id=practice_id,
                 cpt_code=cpt_code,
                 feature_count=len(features))
    
    return features


def compute_rolling_denial_rate(
    denial_records: list[DenialRateRecord],
    window_days: int = 90,
) -> float:
    """Compute rolling denial rate from historical records.
    
    Args:
        denial_records: List of denial rate records
        window_days: Time window in days
        
    Returns:
        Average denial rate over the window
    """
    if not denial_records:
        return 0.0
    
    total_denied = sum(r.denied_claims for r in denial_records)
    total_claims = sum(r.total_claims for r in denial_records)
    
    if total_claims == 0:
        return 0.0
    
    return float(total_denied / total_claims)
