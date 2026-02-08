"""Optimized feature engineering with batching and caching.

This version batches database calls and caches historical features
to dramatically improve performance for large claim sets.
"""

from datetime import date, timedelta
from typing import Optional
import pandas as pd
import structlog
from collections import defaultdict
import asyncio

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


async def engineer_features_batch_optimized(
    claims: list[Claim],
    repository: ClaimsRepository,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """Optimized batch feature engineering with batching and caching.
    
    This version:
    1. Batches all database calls (line items, denial details)
    2. Caches historical features by unique combinations
    3. Uses asyncio.gather for parallel processing
    
    Args:
        claims: List of claim objects
        repository: Claims repository
        reference_date: Reference date for calculations
        
    Returns:
        DataFrame with one row per claim and features as columns
    """
    if reference_date is None:
        reference_date = date.today()
    
    if not claims:
        return pd.DataFrame()
    
    logger.info("Starting optimized batch feature engineering", 
                claim_count=len(claims))
    
    # Step 1: Batch fetch all line items and denial details
    claim_ids = [c.claim_id for c in claims]
    
    logger.info("📥 Step 1/4: Batch fetching line items and denial details",
                total_claims=len(claim_ids))
    
    line_items_tasks = [repository.get_claim_line_items(cid) for cid in claim_ids]
    denial_details_tasks = [repository.get_denial_details(cid) for cid in claim_ids]
    
    # Fetch in parallel
    line_items_results, denial_details_results = await asyncio.gather(
        asyncio.gather(*line_items_tasks),
        asyncio.gather(*denial_details_tasks),
    )
    
    # Create lookup dictionaries
    line_items_by_claim = dict(zip(claim_ids, line_items_results))
    denial_details_by_claim = dict(zip(claim_ids, denial_details_results))
    
    total_line_items = sum(len(li) for li in line_items_results)
    total_denial_details = sum(len(dd) for dd in denial_details_results)
    logger.info("✅ Step 1/4: Completed fetching line items and denial details",
                line_items_count=total_line_items,
                denial_details_count=total_denial_details,
                avg_line_items_per_claim=f"{total_line_items/len(claims):.1f}" if claims else "0")
    
    # Step 2: Identify unique combinations for historical features
    # This avoids fetching the same historical data multiple times
    logger.info("📊 Step 2/4: Identifying unique combinations for historical features")
    
    unique_combinations = {
        'cpt_payer': set(),
        'practice': set(),
        'provider': set(),
    }
    
    # First pass: extract primary CPT codes from line items
    primary_cpt_by_claim = {}
    for claim in claims:
        if claim.claim_id in line_items_by_claim:
            line_items = line_items_by_claim[claim.claim_id]
            if line_items and hasattr(line_items[0], 'cpt_code'):
                primary_cpt = line_items[0].cpt_code
                # Handle format like "HC:92507:GN" - extract middle part
                if primary_cpt and ":" in primary_cpt:
                    parts = primary_cpt.split(":")
                    primary_cpt = parts[1] if len(parts) > 1 else primary_cpt
                primary_cpt_by_claim[claim.claim_id] = primary_cpt
    
    # Build unique combinations
    for claim in claims:
        primary_cpt = primary_cpt_by_claim.get(claim.claim_id)
        if primary_cpt and claim.payer_id:
            unique_combinations['cpt_payer'].add((primary_cpt, claim.payer_id))
        if claim.practice_id:
            unique_combinations['practice'].add(str(claim.practice_id))
        if claim.provider_id:
            unique_combinations['provider'].add(claim.provider_id)
    
    logger.info("✅ Step 2/4: Identified unique combinations",
                cpt_payer_combos=len(unique_combinations['cpt_payer']),
                practices=len(unique_combinations['practice']),
                providers=len(unique_combinations['provider']))
    
    # Step 3: Pre-fetch all historical denial rates
    logger.info("📥 Step 3/4: Pre-fetching historical denial rates",
                cpt_payer_combos=len(unique_combinations['cpt_payer']),
                practices=len(unique_combinations['practice']),
                providers=len(unique_combinations['provider']))
    
    historical_cache = {}
    date_from = reference_date - timedelta(days=365)
    
    # Fetch CPT-payer combinations
    if unique_combinations['cpt_payer']:
        cpt_payer_records = await repository.get_historical_denial_rates(
            group_by=["cpt_code", "payer_id"],
            date_from=date_from,
            date_to=reference_date,
        )
        cached_count = 0
        for record in cpt_payer_records:
            key = (record.group_key.get("cpt_code"), record.group_key.get("payer_id"))
            if key in unique_combinations['cpt_payer']:
                historical_cache[('cpt_payer', key)] = record
                cached_count += 1
        logger.debug("Cached CPT-payer combinations", cached=cached_count, total=len(cpt_payer_records))
    
    # Fetch practice-level
    if unique_combinations['practice']:
        practice_records = await repository.get_historical_denial_rates(
            group_by=["practice_id"],
            date_from=date_from,
            date_to=reference_date,
        )
        cached_count = 0
        for record in practice_records:
            key = record.group_key.get("practice_id")
            if key in unique_combinations['practice']:
                historical_cache[('practice', key)] = record
                cached_count += 1
        logger.debug("Cached practice-level rates", cached=cached_count, total=len(practice_records))
    
    # Fetch provider-level
    if unique_combinations['provider']:
        provider_records = await repository.get_historical_denial_rates(
            group_by=["provider_id"],
            date_from=date_from,
            date_to=reference_date,
        )
        cached_count = 0
        for record in provider_records:
            key = record.group_key.get("provider_id")
            if key in unique_combinations['provider']:
                historical_cache[('provider', key)] = record
                cached_count += 1
        logger.debug("Cached provider-level rates", cached=cached_count, total=len(provider_records))
    
    logger.info("✅ Step 3/4: Completed pre-fetching historical denial rates",
                cache_size=len(historical_cache))
    
    # Step 4: Process claims (now much faster since data is pre-fetched)
    logger.info("⚙️  Step 4/4: Processing claims and engineering features",
                total_claims=len(claims))
    
    feature_rows = []
    progress_interval = max(1, len(claims) // 20)  # Log every 5% progress
    
    for idx, claim in enumerate(claims):
        # Log progress
        if (idx + 1) % progress_interval == 0 or (idx + 1) == len(claims):
            progress_pct = ((idx + 1) / len(claims)) * 100
            logger.info("Processing claims", 
                       progress=f"{idx + 1}/{len(claims)} ({progress_pct:.1f}%)",
                       successful=len(feature_rows))
        try:
            line_items = line_items_by_claim.get(claim.claim_id, [])
            denial_details = denial_details_by_claim.get(claim.claim_id, [])
            
            # Extract claim-level features
            claim_features = extract_claim_features(claim, line_items)
            
            # Extract CPT-specific features (use cached primary CPT if available)
            primary_cpt = claim_features.get("primary_cpt_code") or primary_cpt_by_claim.get(claim.claim_id)
            if primary_cpt:
                cpt_features = extract_cpt_features(primary_cpt)
                claim_features.update(cpt_features)
            
            # Extract temporal features
            service_date = claim_features.get("service_date")
            submitted_date = claim_features.get("submitted_date")
            temporal_features = extract_temporal_features(
                service_date=service_date,
                submitted_date=submitted_date,
                reference_date=reference_date,
            )
            claim_features.update(temporal_features)
            
            # Process denial details (already fetched)
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
            
            claim_features["denial_detail_count"] = len(denial_details)
            claim_features["has_adjustments"] = len(denial_details) > 0
            claim_features["unique_carc_count"] = len(set(carc_codes))
            claim_features["unique_rarc_count"] = len(set(rarc_codes))
            claim_features["total_adjustment_from_details"] = total_adjustment_from_details
            
            # Extract CPT-CARC/RARC interaction features (for DENIALS)
            # Denials have CARC/RARC codes from the payer
            from src.pipelines.feature_engineering.cpt_carc_interactions import (
                extract_cpt_carc_interaction_features,
            )
            
            line_items = line_items_by_claim.get(claim.claim_id, [])
            interaction_features = extract_cpt_carc_interaction_features(
                claim=claim,
                line_items=line_items,
                denial_details=denial_details,
                primary_cpt=primary_cpt,
            )
            claim_features.update(interaction_features)
            
            # Extract rejection pattern features (for REJECTIONS)
            # Rejections are based on missing/incorrect claim fields, not CARC/RARC codes
            from src.pipelines.feature_engineering.rejection_patterns import (
                extract_rejection_pattern_features,
            )
            
            rejection_features = extract_rejection_pattern_features(
                claim=claim,
                line_items=line_items,
                primary_cpt=primary_cpt,
            )
            claim_features.update(rejection_features)
            
            # Determine if claim is denied
            # A claim is considered "denied" if:
            # 1. Status is explicitly DENIED (full denial)
            # 2. Has denial details and status is not PAID (full denial with details)
            # 3. Is partially paid with SIGNIFICANT denial adjustments (payment < 50% of billed)
            #    Note: Fee schedule adjustments (CARC 45) alone don't count as denials unless payment is very low
            is_fully_denied = (claim.status == ClaimStatus.DENIED)
            has_denial_details_not_paid = (denial_details and claim.status != ClaimStatus.PAID)
            
            # Check for partial denial (paid but with very low payment ratio)
            # This captures cases where the claim was "paid" but most of it was denied/adjusted
            is_partially_denied = False
            if claim.status == ClaimStatus.PAID and claim.total_billed_amount and claim.total_paid_amount:
                billed = float(claim.total_billed_amount)
                paid = float(claim.total_paid_amount)
                payment_ratio = paid / billed if billed > 0 else 0.0
                
                # Only count as denied if payment ratio is very low (< 50%)
                # This indicates a significant portion was denied, not just routine fee schedule adjustments
                if payment_ratio < 0.50:
                    is_partially_denied = True
            
            claim_features["is_denied"] = is_fully_denied or has_denial_details_not_paid or is_partially_denied
            
            claim_features["is_rejected"] = (claim.status == ClaimStatus.REJECTED) if claim.status else False
            
            # Partial payment features
            claim_features["is_partially_paid"] = (
                claim_features.get("total_paid_amount", 0) > 0 
                and claim_features.get("total_billed_amount", 0) > 0 
                and claim_features.get("payment_ratio", 0) < 1.0
            )
            claim_features["adjustment_amount"] = (
                claim_features.get("total_billed_amount", 0) - claim_features.get("total_paid_amount", 0)
            )
            if claim_features.get("total_billed_amount", 0) > 0:
                claim_features["adjustment_ratio"] = (
                    claim_features["adjustment_amount"] / claim_features["total_billed_amount"]
                )
            else:
                claim_features["adjustment_ratio"] = 0.0
            
            claim_features["has_partial_denial"] = (
                claim_features.get("is_partially_paid", False) 
                and claim_features.get("has_adjustments", False)
            )
            
            # Extract historical features from cache (no DB calls!)
            historical_features = {}
            
            # CPT-Payer combination
            if primary_cpt and claim.payer_id:
                key = ('cpt_payer', (primary_cpt, claim.payer_id))
                if key in historical_cache:
                    record = historical_cache[key]
                    historical_features["hist_denial_rate_cpt_payer"] = record.denial_rate
                    historical_features["hist_denial_count_cpt_payer"] = record.denied_claims
                    historical_features["hist_total_claims_cpt_payer"] = record.total_claims
                else:
                    historical_features["hist_denial_rate_cpt_payer"] = 0.0
                    historical_features["hist_denial_count_cpt_payer"] = 0
                    historical_features["hist_total_claims_cpt_payer"] = 0
            
            # Practice-level
            if claim.practice_id:
                key = ('practice', claim.practice_id)
                if key in historical_cache:
                    record = historical_cache[key]
                    historical_features["hist_denial_rate_practice"] = record.denial_rate
                    historical_features["hist_denial_count_practice"] = record.denied_claims
                    historical_features["hist_total_claims_practice"] = record.total_claims
                else:
                    historical_features["hist_denial_rate_practice"] = 0.0
                    historical_features["hist_denial_count_practice"] = 0
                    historical_features["hist_total_claims_practice"] = 0
            
            # Provider-level
            if claim.provider_id:
                key = ('provider', claim.provider_id)
                if key in historical_cache:
                    record = historical_cache[key]
                    historical_features["hist_denial_rate_provider"] = record.denial_rate
                    historical_features["hist_denial_count_provider"] = record.denied_claims
                    historical_features["hist_total_claims_provider"] = record.total_claims
                else:
                    historical_features["hist_denial_rate_provider"] = 0.0
                    historical_features["hist_denial_count_provider"] = 0
                    historical_features["hist_total_claims_provider"] = 0
            
            # Time-windowed counts (simplified - could be optimized further)
            # For now, we'll use the same cache but could add separate queries
            for window in [90, 180, 365]:
                if primary_cpt and claim.payer_id:
                    # Use the 365d data as approximation for now
                    # Could be optimized with separate cache entries
                    key = ('cpt_payer', (primary_cpt, claim.payer_id))
                    if key in historical_cache:
                        record = historical_cache[key]
                        historical_features[f"hist_denial_count_cpt_payer_{window}d"] = record.denied_claims
                        historical_features[f"hist_total_claims_cpt_payer_{window}d"] = record.total_claims
                    else:
                        historical_features[f"hist_denial_count_cpt_payer_{window}d"] = 0
                        historical_features[f"hist_total_claims_cpt_payer_{window}d"] = 0
            
            claim_features.update(historical_features)
            claim_features["claim_id"] = claim.claim_id
            
            feature_rows.append(claim_features)
            
        except Exception as e:
            logger.error("Failed to engineer features for claim",
                        claim_id=claim.claim_id,
                        error=str(e))
            continue
    
    if not feature_rows:
        logger.warning("No features extracted from claims", claim_count=len(claims))
        return pd.DataFrame()
    
    logger.info("📊 Creating feature DataFrame...")
    df = pd.DataFrame(feature_rows)
    
    logger.info("✅ Step 4/4: Completed feature engineering",
                total_claims=len(claims),
                successful=len(feature_rows),
                failed=len(claims) - len(feature_rows),
                feature_count=len(df.columns) if not df.empty else 0)
    
    return df

