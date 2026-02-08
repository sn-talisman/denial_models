"""Analytics endpoints for practice and payer analysis."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
import pandas as pd
import structlog
from pathlib import Path
from datetime import date, timedelta
import asyncio
from collections import defaultdict

from src.api.routes.predictions import get_predictor
from src.data_access.factory import get_repository
from src.models.denial_predictor.predictor import DenialPredictor
from src.data_access.factory import get_repository
from src.pipelines.feature_engineering.feature_engineer_optimized import engineer_features_batch_optimized as engineer_features_batch
from src.api.analytics_helpers import (
    get_practice_data,
    calculate_performance_summary,
    get_prioritized_action_items as get_action_items_helper,
    get_payer_performance,
    get_cpt_performance,
    get_high_risk_claims,
    get_carc_rarc_analysis,
    get_cpt_carc_correlation,
    get_rejection_pattern_analysis,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


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


@router.get("/practices", response_model=list[PracticeAnalysisResponse])
async def analyze_practices(
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    min_claims: int = Query(default=5, ge=1, description="Minimum claims required for inclusion"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> list[PracticeAnalysisResponse]:
    """Analyze denial and rejection rates by practice.
    
    Args:
        days_back: Number of days to analyze
        min_claims: Minimum number of claims required
        predictor: Predictor instance (injected)
        
    Returns:
        List of practice-level analysis results
    """
    try:
        repository = get_repository()
        
        try:
            date_to = date.today()
            date_from = date_to - timedelta(days=days_back)
            
            # Fetch claims
            claims = await repository.get_claims(
                date_from=date_from,
                date_to=date_to,
            )
            
            if not claims:
                return []
            
            # Engineer features
            df = await engineer_features_batch(
                claims=claims,
                repository=repository,
                reference_date=date_to,
            )
            
            if df.empty:
                return []
            
            # Make predictions
            exclude_cols = ['claim_id', 'claim_number', 'service_date', 'submitted_date', 
                           'adjudicated_date', 'primary_cpt_code', 'claim_status', 
                           'cpt_code', 'cpt_category', 'is_denied']
            feature_cols = [c for c in df.columns if c not in exclude_cols]
            features_df = df[feature_cols].copy()
            
            # Convert object columns to numeric
            for col in features_df.columns:
                if features_df[col].dtype == 'object':
                    try:
                        features_df[col] = pd.to_numeric(features_df[col], errors='coerce')
                    except:
                        pass
            
            # Fill NaN values and ensure numeric types
            features_df = features_df.fillna(0)
            for col in features_df.columns:
                if features_df[col].dtype == 'object':
                    features_df[col] = features_df[col].astype(float)
            
            predictions_df = predictor.predict_batch(features_df)
            
            # Create mapping from claim_id to practice_id and payer_id
            claim_to_practice = {c.claim_id: c.practice_id for c in claims}
            claim_to_payer = {c.claim_id: c.payer_id for c in claims}
            
            # Add original data
            predictions_df['claim_id'] = df['claim_id'].values
            predictions_df['practice_id'] = predictions_df['claim_id'].map(claim_to_practice)
            predictions_df['is_denied'] = df['is_denied'].values if 'is_denied' in df.columns else [False] * len(df)
            predictions_df['is_rejected'] = df['is_rejected'].values if 'is_rejected' in df.columns else [False] * len(df)
            predictions_df['total_billed_amount'] = df['total_billed_amount'].values if 'total_billed_amount' in df.columns else [0] * len(df)
            
            # Get practice names
            practices = await repository.get_practices()
            practice_map = {p.practice_id: p.name for p in practices}
            predictions_df['practice_name'] = predictions_df['practice_id'].map(practice_map)
            
            # Analyze by practice
            results = []
            for practice_id in predictions_df['practice_id'].dropna().unique():
                practice_data = predictions_df[predictions_df['practice_id'] == practice_id]
                
                if len(practice_data) < min_claims:
                    continue
                
                practice_name_val = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else None
                practice_name = str(practice_name_val) if pd.notna(practice_name_val) else "Unknown"
                total = len(practice_data)
                denied = practice_data['is_denied'].sum()
                rejected = practice_data['is_rejected'].sum()
                denied_or_rejected = (practice_data['is_denied'] | practice_data['is_rejected']).sum()
                
                high_risk = (practice_data['risk_level'] == 'high').sum()
                medium_risk = (practice_data['risk_level'] == 'medium').sum()
                low_risk = (practice_data['risk_level'] == 'low').sum()
                avg_probability = practice_data['denial_probability'].mean()
                
                total_billed = practice_data['total_billed_amount'].sum()
                denied_billed = practice_data[practice_data['is_denied']]['total_billed_amount'].sum()
                
                results.append(PracticeAnalysisResponse(
                    practice_id=str(practice_id),
                    practice_name=practice_name,
                    total_claims=total,
                    denied_claims=int(denied),
                    rejected_claims=int(rejected),
                    denied_or_rejected=int(denied_or_rejected),
                    denial_rate=float(denied / total if total > 0 else 0),
                    rejection_rate=float(rejected / total if total > 0 else 0),
                    denial_or_rejection_rate=float(denied_or_rejected / total if total > 0 else 0),
                    avg_denial_probability=float(avg_probability),
                    high_risk_count=int(high_risk),
                    medium_risk_count=int(medium_risk),
                    low_risk_count=int(low_risk),
                    high_risk_pct=float(high_risk / total if total > 0 else 0),
                    total_billed=float(total_billed),
                    denied_billed=float(denied_billed),
                    denied_billed_pct=float(denied_billed / total_billed if total_billed > 0 else 0),
                ))
            
            # Sort by denial rate
            results.sort(key=lambda x: x.denial_rate, reverse=True)
            
            await repository.close()
            return results
            
        finally:
            await repository.close()
            
    except Exception as e:
        logger.error("Error in practice analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/payers", response_model=list[PayerAnalysisResponse])
async def analyze_payers(
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    min_claims: int = Query(default=5, ge=1, description="Minimum claims required for inclusion"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> list[PayerAnalysisResponse]:
    """Analyze denial and rejection rates by payer.
    
    Args:
        days_back: Number of days to analyze
        min_claims: Minimum number of claims required
        predictor: Predictor instance (injected)
        
    Returns:
        List of payer-level analysis results
    """
    try:
        repository = get_repository()
        
        try:
            date_to = date.today()
            date_from = date_to - timedelta(days=days_back)
            
            # Fetch claims
            claims = await repository.get_claims(
                date_from=date_from,
                date_to=date_to,
            )
            
            if not claims:
                return []
            
            # Engineer features
            df = await engineer_features_batch(
                claims=claims,
                repository=repository,
                reference_date=date_to,
            )
            
            if df.empty:
                return []
            
            # Make predictions
            exclude_cols = ['claim_id', 'claim_number', 'service_date', 'submitted_date', 
                           'adjudicated_date', 'primary_cpt_code', 'claim_status', 
                           'cpt_code', 'cpt_category', 'is_denied']
            feature_cols = [c for c in df.columns if c not in exclude_cols]
            features_df = df[feature_cols].copy()
            
            # Convert object columns to numeric
            for col in features_df.columns:
                if features_df[col].dtype == 'object':
                    try:
                        features_df[col] = pd.to_numeric(features_df[col], errors='coerce')
                    except:
                        pass
            
            # Fill NaN values and ensure numeric types
            features_df = features_df.fillna(0)
            for col in features_df.columns:
                if features_df[col].dtype == 'object':
                    features_df[col] = features_df[col].astype(float)
            
            predictions_df = predictor.predict_batch(features_df)
            
            # Add original data
            predictions_df['payer_id'] = df.get('payer_id', [None] * len(df))
            predictions_df['is_denied'] = df['is_denied'].values if 'is_denied' in df.columns else [False] * len(df)
            predictions_df['is_rejected'] = df['is_rejected'].values if 'is_rejected' in df.columns else [False] * len(df)
            predictions_df['total_billed_amount'] = df['total_billed_amount'].values if 'total_billed_amount' in df.columns else [0] * len(df)
            
            # Get payer names
            payers = await repository.get_payers()
            payer_map = {p.payer_id: p.name for p in payers}
            predictions_df['payer_name'] = predictions_df['payer_id'].map(payer_map)
            
            # Analyze by payer
            results = []
            for payer_id in predictions_df['payer_id'].dropna().unique():
                payer_data = predictions_df[predictions_df['payer_id'] == payer_id]
                
                if len(payer_data) < min_claims:
                    continue
                
                payer_name_val = payer_data['payer_name'].iloc[0] if len(payer_data) > 0 else None
                payer_name = str(payer_name_val) if pd.notna(payer_name_val) else "Unknown"
                total = len(payer_data)
                denied = payer_data['is_denied'].sum()
                rejected = payer_data['is_rejected'].sum()
                denied_or_rejected = (payer_data['is_denied'] | payer_data['is_rejected']).sum()
                
                high_risk = (payer_data['risk_level'] == 'high').sum()
                medium_risk = (payer_data['risk_level'] == 'medium').sum()
                low_risk = (payer_data['risk_level'] == 'low').sum()
                avg_probability = payer_data['denial_probability'].mean()
                
                total_billed = payer_data['total_billed_amount'].sum()
                denied_billed = payer_data[payer_data['is_denied']]['total_billed_amount'].sum()
                
                results.append(PayerAnalysisResponse(
                    payer_id=str(payer_id),
                    payer_name=payer_name,
                    total_claims=total,
                    denied_claims=int(denied),
                    rejected_claims=int(rejected),
                    denied_or_rejected=int(denied_or_rejected),
                    denial_rate=float(denied / total if total > 0 else 0),
                    rejection_rate=float(rejected / total if total > 0 else 0),
                    denial_or_rejection_rate=float(denied_or_rejected / total if total > 0 else 0),
                    avg_denial_probability=float(avg_probability),
                    high_risk_count=int(high_risk),
                    medium_risk_count=int(medium_risk),
                    low_risk_count=int(low_risk),
                    high_risk_pct=float(high_risk / total if total > 0 else 0),
                    total_billed=float(total_billed),
                    denied_billed=float(denied_billed),
                    denied_billed_pct=float(denied_billed / total_billed if total_billed > 0 else 0),
                ))
            
            # Sort by denial rate
            results.sort(key=lambda x: x.denial_rate, reverse=True)
            
            await repository.close()
            return results
            
        finally:
            await repository.close()
            
    except Exception as e:
        logger.error("Error in payer analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/practice-payer", response_model=list[PracticePayerComboResponse])
async def analyze_practice_payer_combos(
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    min_claims: int = Query(default=5, ge=1, description="Minimum claims required for inclusion"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> list[PracticePayerComboResponse]:
    """Analyze denial and rejection rates by practice-payer combinations.
    
    Args:
        days_back: Number of days to analyze
        min_claims: Minimum number of claims required
        predictor: Predictor instance (injected)
        
    Returns:
        List of practice-payer combination analysis results
    """
    try:
        repository = get_repository()
        
        try:
            date_to = date.today()
            date_from = date_to - timedelta(days=days_back)
            
            # Fetch claims
            claims = await repository.get_claims(
                date_from=date_from,
                date_to=date_to,
            )
            
            if not claims:
                return []
            
            # Engineer features
            df = await engineer_features_batch(
                claims=claims,
                repository=repository,
                reference_date=date_to,
            )
            
            if df.empty:
                return []
            
            # Make predictions
            exclude_cols = ['claim_id', 'claim_number', 'service_date', 'submitted_date', 
                           'adjudicated_date', 'primary_cpt_code', 'claim_status', 
                           'cpt_code', 'cpt_category', 'is_denied']
            feature_cols = [c for c in df.columns if c not in exclude_cols]
            features_df = df[feature_cols].copy()
            
            # Convert object columns to numeric
            for col in features_df.columns:
                if features_df[col].dtype == 'object':
                    try:
                        features_df[col] = pd.to_numeric(features_df[col], errors='coerce')
                    except:
                        pass
            
            # Fill NaN values and ensure numeric types
            features_df = features_df.fillna(0)
            for col in features_df.columns:
                if features_df[col].dtype == 'object':
                    features_df[col] = features_df[col].astype(float)
            
            predictions_df = predictor.predict_batch(features_df)
            
            # Add original data
            predictions_df['practice_id'] = df.get('practice_id', [None] * len(df))
            predictions_df['payer_id'] = df.get('payer_id', [None] * len(df))
            predictions_df['is_denied'] = df['is_denied'].values if 'is_denied' in df.columns else [False] * len(df)
            predictions_df['is_rejected'] = df['is_rejected'].values if 'is_rejected' in df.columns else [False] * len(df)
            predictions_df['total_billed_amount'] = df['total_billed_amount'].values if 'total_billed_amount' in df.columns else [0] * len(df)
            
            # Get names
            practices = await repository.get_practices()
            payers = await repository.get_payers()
            practice_map = {p.practice_id: p.name for p in practices}
            payer_map = {p.payer_id: p.name for p in payers}
            predictions_df['practice_name'] = predictions_df['practice_id'].map(practice_map)
            predictions_df['payer_name'] = predictions_df['payer_id'].map(payer_map)
            
            # Analyze by practice-payer combination
            results = []
            for (practice_id, payer_id), combo_data in predictions_df.groupby(['practice_id', 'payer_id']):
                if pd.isna(practice_id) or pd.isna(payer_id) or len(combo_data) < min_claims:
                    continue
                
                practice_name_val = combo_data['practice_name'].iloc[0] if len(combo_data) > 0 else None
                practice_name = str(practice_name_val) if pd.notna(practice_name_val) else "Unknown"
                payer_name_val = combo_data['payer_name'].iloc[0] if len(combo_data) > 0 else None
                payer_name = str(payer_name_val) if pd.notna(payer_name_val) else "Unknown"
                
                total = len(combo_data)
                denied = combo_data['is_denied'].sum()
                rejected = combo_data['is_rejected'].sum()
                denied_or_rejected = (combo_data['is_denied'] | combo_data['is_rejected']).sum()
                
                high_risk = (combo_data['risk_level'] == 'high').sum()
                avg_probability = combo_data['denial_probability'].mean()
                
                total_billed = combo_data['total_billed_amount'].sum()
                denied_billed = combo_data[combo_data['is_denied']]['total_billed_amount'].sum()
                
                results.append(PracticePayerComboResponse(
                    practice_id=str(practice_id),
                    practice_name=practice_name,
                    payer_id=str(payer_id),
                    payer_name=payer_name,
                    total_claims=total,
                    denied_claims=int(denied),
                    rejected_claims=int(rejected),
                    denied_or_rejected=int(denied_or_rejected),
                    denial_rate=float(denied / total if total > 0 else 0),
                    rejection_rate=float(rejected / total if total > 0 else 0),
                    denial_or_rejection_rate=float(denied_or_rejected / total if total > 0 else 0),
                    avg_denial_probability=float(avg_probability),
                    high_risk_count=int(high_risk),
                    high_risk_pct=float(high_risk / total if total > 0 else 0),
                    total_billed=float(total_billed),
                    denied_billed=float(denied_billed),
                    denied_billed_pct=float(denied_billed / total_billed if total_billed > 0 else 0),
                ))
            
            # Sort by denial rate
            results.sort(key=lambda x: x.denial_rate, reverse=True)
            
            await repository.close()
            return results
            
        finally:
            await repository.close()
            
    except Exception as e:
        logger.error("Error in practice-payer analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# New practice-specific analytics endpoints

class PerformanceInsights(BaseModel):
    """Performance insights."""
    trends: dict = {}
    comparisons: dict = {}
    key_issues: List[str] = []
    risk_factors: List[str] = []


class PerformanceSummaryResponse(BaseModel):
    """Performance summary response."""
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
    """Action item response."""
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
    """Prioritized action items response."""
    practice_id: str
    practice_name: str
    action_items: List[ActionItemResponse]


class PayerPerformanceItem(BaseModel):
    """Payer performance item."""
    payer_name: str
    total_claims: int
    denied_claims: int
    denial_rate: float
    total_billed: float
    total_paid: float
    denied_amount: float
    avg_denial_probability: float


class PayerPerformanceResponse(BaseModel):
    """Payer performance response."""
    practice_id: str
    practice_name: str
    payers: List[PayerPerformanceItem]


class CPTPerformanceItem(BaseModel):
    """CPT performance item."""
    cpt_code: str
    total_claims: int
    denied_claims: int
    denial_rate: float
    total_billed: float
    denied_amount: float
    avg_denial_probability: float


class CPTPerformanceResponse(BaseModel):
    """CPT performance response."""
    practice_id: str
    practice_name: str
    cpt_codes: List[CPTPerformanceItem]


class HighRiskClaimItem(BaseModel):
    """High risk claim item."""
    claim_id: Optional[str]
    payer_name: str
    cpt_code: Optional[str]
    denial_probability: float
    billed_amount: float
    is_denied: bool


class HighRiskClaimsResponse(BaseModel):
    """High risk claims response."""
    practice_id: str
    practice_name: str
    high_risk_claims: List[HighRiskClaimItem]


@router.get("/practice/{practice_guid}/performance-summary", response_model=PerformanceSummaryResponse)
async def get_performance_summary(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> PerformanceSummaryResponse:
    """Get performance summary for a specific practice.
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        predictor: Predictor instance (injected)
        
    Returns:
        Performance summary for the practice
    """
    try:
        repository = get_repository()
        
        try:
            # Get practice data
            practice_data = await get_practice_data(practice_guid, days_back, repository, predictor)
            
            if practice_data.empty:
                raise HTTPException(status_code=404, detail=f"No claims found for practice {practice_guid}")
            
            # For overall benchmarks, we'll use a simple default (can be enhanced later)
            # In a production system, you might cache these values or calculate them periodically
            overall_denial_rate = 0.24  # Default benchmark (24% denial rate)
            overall_avg_prob = 0.10  # Default benchmark (10% avg probability)
            
            # Calculate summary
            summary = calculate_performance_summary(practice_data, overall_denial_rate, overall_avg_prob)
            
            practice_name = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else "Unknown"
            
            # Convert insights dict to PerformanceInsights model
            insights_dict = summary.pop('insights', {})
            insights = PerformanceInsights(**insights_dict)
            
            return PerformanceSummaryResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                insights=insights,
                **summary
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in performance summary", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/practice/{practice_guid}/action-items", response_model=PrioritizedActionItemsResponse)
async def get_prioritized_action_items(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> PrioritizedActionItemsResponse:
    """Get prioritized action items for a specific practice.
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        predictor: Predictor instance (injected)
        
    Returns:
        Prioritized action items for the practice
    """
    try:
        repository = get_repository()
        
        try:
            # Get practice data
            practice_data = await get_practice_data(practice_guid, days_back, repository, predictor)
            
            if practice_data.empty:
                raise HTTPException(status_code=404, detail=f"No claims found for practice {practice_guid}")
            
            # Get CARC/RARC and CPT-CARC data for enhanced insights
            carc_rarc_data = await get_carc_rarc_analysis(practice_guid, days_back, repository)
            cpt_carc_data = await get_cpt_carc_correlation(practice_guid, days_back, repository)
            
            # Get action items with enhanced insights
            action_items = get_action_items_helper(
                practice_data,
                carc_rarc_data=carc_rarc_data,
                cpt_carc_data=cpt_carc_data,
            )
            
            practice_name = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else "Unknown"
            
            return PrioritizedActionItemsResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                action_items=[ActionItemResponse(**item) for item in action_items]
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in action items", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/practice/{practice_guid}/payer-performance", response_model=PayerPerformanceResponse)
async def get_practice_payer_performance(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> PayerPerformanceResponse:
    """Get payer performance breakdown for a specific practice.
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        predictor: Predictor instance (injected)
        
    Returns:
        Payer performance breakdown for the practice
    """
    try:
        repository = get_repository()
        
        try:
            # Get practice data
            practice_data = await get_practice_data(practice_guid, days_back, repository, predictor)
            
            if practice_data.empty:
                raise HTTPException(status_code=404, detail=f"No claims found for practice {practice_guid}")
            
            # Get payer performance
            payer_perf = get_payer_performance(practice_data)
            
            practice_name = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else "Unknown"
            
            return PayerPerformanceResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                payers=[PayerPerformanceItem(**item) for item in payer_perf]
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in payer performance", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/practice/{practice_guid}/cpt-performance", response_model=CPTPerformanceResponse)
async def get_practice_cpt_performance(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> CPTPerformanceResponse:
    """Get CPT code performance breakdown for a specific practice.
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        predictor: Predictor instance (injected)
        
    Returns:
        CPT code performance breakdown for the practice
    """
    try:
        repository = get_repository()
        
        try:
            # Get practice data
            practice_data = await get_practice_data(practice_guid, days_back, repository, predictor)
            
            if practice_data.empty:
                raise HTTPException(status_code=404, detail=f"No claims found for practice {practice_guid}")
            
            # Get CPT performance
            cpt_perf = get_cpt_performance(practice_data)
            
            practice_name = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else "Unknown"
            
            return CPTPerformanceResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                cpt_codes=[CPTPerformanceItem(**item) for item in cpt_perf]
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in CPT performance", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/practice/{practice_guid}/high-risk-claims", response_model=HighRiskClaimsResponse)
async def get_practice_high_risk_claims(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of claims to return"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> HighRiskClaimsResponse:
    """Get high-risk claims for a specific practice.
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        limit: Maximum number of claims to return
        predictor: Predictor instance (injected)
        
    Returns:
        High-risk claims for the practice
    """
    try:
        repository = get_repository()
        
        try:
            # Get practice data
            practice_data = await get_practice_data(practice_guid, days_back, repository, predictor)
            
            if practice_data.empty:
                raise HTTPException(status_code=404, detail=f"No claims found for practice {practice_guid}")
            
            # Get high-risk claims
            high_risk = get_high_risk_claims(practice_data, limit=limit)
            
            practice_name = practice_data['practice_name'].iloc[0] if len(practice_data) > 0 else "Unknown"
            
            return HighRiskClaimsResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                high_risk_claims=[HighRiskClaimItem(**item) for item in high_risk]
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in high-risk claims", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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
    """CARC/RARC analysis response."""
    practice_id: str
    practice_name: str
    carc_codes: List[CARCCodeItem]
    rarc_codes: List[RARCCodeItem]


@router.get("/practice/{practice_guid}/denial-reasons", response_model=CARCRARCAnalysisResponse)
async def get_denial_reasons_analysis(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
) -> CARCRARCAnalysisResponse:
    """Get CARC/RARC code analysis for a specific practice.
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        
    Returns:
        CARC/RARC code analysis for the practice
    """
    try:
        repository = get_repository()
        
        try:
            # Get CARC/RARC analysis
            analysis = await get_carc_rarc_analysis(practice_guid, days_back, repository)
            
            # Get practice name
            practices = await repository.get_practices()
            practice_map = {p.practice_id: p.name for p in practices}
            practice_name = practice_map.get(practice_guid, "Unknown")
            
            return CARCRARCAnalysisResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                carc_codes=[CARCCodeItem(**item) for item in analysis['carc_codes']],
                rarc_codes=[RARCCodeItem(**item) for item in analysis['rarc_codes']],
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in denial reasons analysis", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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
    """CPT-CARC/RARC correlation response."""
    practice_id: str
    practice_name: str
    cpt_carc: List[CPTCARCCorrelationItem]
    cpt_rarc: List[CPTRARCCorrelationItem]


@router.get("/practice/{practice_guid}/cpt-carc-correlation", response_model=CPTCARCCorrelationResponse)
async def get_cpt_carc_correlation_endpoint(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
) -> CPTCARCCorrelationResponse:
    """Get CPT-CARC/RARC correlation analysis for a specific practice.
    
    Shows which procedure codes are most commonly associated with which
    denial reason codes, helping identify root causes.
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        
    Returns:
        CPT-CARC/RARC correlation analysis
    """
    try:
        repository = get_repository()
        
        try:
            # Get CPT-CARC correlation
            correlation = await get_cpt_carc_correlation(practice_guid, days_back, repository)
            
            # Get practice name
            practices = await repository.get_practices()
            practice_map = {p.practice_id: p.name for p in practices}
            practice_name = practice_map.get(practice_guid, "Unknown")
            
            return CPTCARCCorrelationResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                cpt_carc=[CPTCARCCorrelationItem(**item) for item in correlation['cpt_carc']],
                cpt_rarc=[CPTRARCCorrelationItem(**item) for item in correlation['cpt_rarc']],
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in CPT-CARC correlation analysis", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


class RejectionPatternItem(BaseModel):
    """Rejection pattern item."""
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
    """Rejection pattern analysis response."""
    practice_id: str
    practice_name: str
    rejection_patterns: List[RejectionPatternItem]


@router.get("/practice/{practice_guid}/rejection-patterns", response_model=RejectionPatternResponse)
async def get_rejection_patterns_endpoint(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
) -> RejectionPatternResponse:
    """Get rejection pattern analysis for a specific practice.
    
    Shows which CPT codes are associated with which rejection issues
    (missing fields, invalid data, etc.).
    
    Args:
        practice_guid: Practice GUID
        days_back: Number of days to analyze
        
    Returns:
        Rejection pattern analysis
    """
    try:
        repository = get_repository()
        
        try:
            # Get rejection pattern analysis
            analysis = await get_rejection_pattern_analysis(practice_guid, days_back, repository)
            
            # Get practice name
            practices = await repository.get_practices()
            practice_map = {p.practice_id: p.name for p in practices}
            practice_name = practice_map.get(practice_guid, "Unknown")
            
            return RejectionPatternResponse(
                practice_id=practice_guid,
                practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
                rejection_patterns=[RejectionPatternItem(**item) for item in analysis['rejection_patterns']],
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in rejection pattern analysis", error=str(e), practice_guid=practice_guid)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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


@router.get("/overall-insights", response_model=OverallInsightsResponse)
async def get_overall_insights(
    days_back: int = Query(default=365, ge=1, le=3650, description="Number of days to look back"),
    predictor: DenialPredictor = Depends(get_predictor),
) -> OverallInsightsResponse:
    """Get overall insights across all practices.
    
    Provides aggregated insights including top denial reasons, payers, and CPT codes
    across all practices in the system.
    
    Args:
        days_back: Number of days to analyze
        predictor: Predictor instance (injected)
        
    Returns:
        Overall insights across all practices
    """
    try:
        repository = get_repository()
        
        try:
            # Get all practices
            practices = await repository.get_practices()
            
            # Aggregate data across all practices
            total_claims = 0
            total_denials = 0
            total_denied_amount = 0.0
            
            carc_aggregate = defaultdict(lambda: {'count': 0, 'amount': 0.0})
            payer_aggregate = defaultdict(lambda: {'claims': 0, 'denials': 0, 'amount': 0.0})
            cpt_aggregate = defaultdict(lambda: {'claims': 0, 'denials': 0, 'amount': 0.0})
            
            for practice in practices:
                try:
                    # Get practice data
                    practice_data = await get_practice_data(practice.practice_id, days_back, repository, predictor)
                    
                    if practice_data.empty:
                        continue
                    
                    total_claims += len(practice_data)
                    denied_count = practice_data['is_denied'].sum()
                    total_denials += denied_count
                    denied_amount = practice_data[practice_data['is_denied']]['total_billed_amount'].sum()
                    total_denied_amount += float(denied_amount)
                    
                    # Get CARC/RARC analysis
                    carc_rarc = await get_carc_rarc_analysis(practice.practice_id, days_back, repository)
                    for carc in carc_rarc.get('carc_codes', [])[:10]:
                        carc_aggregate[carc['carc_code']]['count'] += carc['occurrence_count']
                        carc_aggregate[carc['carc_code']]['amount'] += carc['total_adjustment_amount']
                    
                    # Get payer performance
                    payer_perf = get_payer_performance(practice_data)
                    for payer in payer_perf[:10]:
                        payer_aggregate[payer['payer_name']]['claims'] += payer['total_claims']
                        payer_aggregate[payer['payer_name']]['denials'] += payer['denied_claims']
                        payer_aggregate[payer['payer_name']]['amount'] += payer['denied_amount']
                    
                    # Get CPT performance
                    cpt_perf = get_cpt_performance(practice_data)
                    for cpt in cpt_perf[:10]:
                        cpt_aggregate[cpt['cpt_code']]['claims'] += cpt['total_claims']
                        cpt_aggregate[cpt['cpt_code']]['denials'] += cpt['denied_claims']
                        cpt_aggregate[cpt['cpt_code']]['amount'] += cpt['denied_amount']
                        
                except Exception as e:
                    logger.warning(f"Error processing practice {practice.practice_id}: {e}")
                    continue
            
            # Calculate overall denial rate
            overall_denial_rate = (total_denials / total_claims) if total_claims > 0 else 0.0
            
            # Get top CARC codes
            top_carcs = sorted(
                [{'carc_code': code, 'occurrence_count': data['count'], 'total_amount': data['amount']}
                 for code, data in carc_aggregate.items()],
                key=lambda x: x['total_amount'],
                reverse=True
            )[:10]
            
            # Get top payers
            top_payers = sorted(
                [{'payer_name': name, 'total_claims': data['claims'], 'denied_claims': data['denials'],
                  'denial_rate': (data['denials'] / data['claims']) if data['claims'] > 0 else 0.0,
                  'denied_amount': data['amount']}
                 for name, data in payer_aggregate.items()],
                key=lambda x: x['denied_amount'],
                reverse=True
            )[:10]
            
            # Get top CPT codes
            top_cpts = sorted(
                [{'cpt_code': code, 'total_claims': data['claims'], 'denied_claims': data['denials'],
                  'denial_rate': (data['denials'] / data['claims']) if data['claims'] > 0 else 0.0,
                  'denied_amount': data['amount']}
                 for code, data in cpt_aggregate.items()],
                key=lambda x: x['denied_amount'],
                reverse=True
            )[:10]
            
            # Generate key findings
            key_findings = []
            if overall_denial_rate > 0.5:
                key_findings.append(f"Overall denial rate is very high ({overall_denial_rate:.1%})")
            if top_carcs:
                top_carc = top_carcs[0]
                from src.utils.constants import COMMON_CARC_CODES
                carc_desc = COMMON_CARC_CODES.get(top_carc['carc_code'], f"CARC {top_carc['carc_code']}")
                key_findings.append(f"Top denial reason: {carc_desc} (${top_carc['total_amount']:,.2f})")
            if top_payers:
                top_payer = top_payers[0]
                key_findings.append(f"Top payer by denial amount: {top_payer['payer_name']} (${top_payer['denied_amount']:,.2f})")
            if total_denied_amount > 0:
                recovery_potential = total_denied_amount * 0.3
                key_findings.append(f"Potential recovery through appeals: ${recovery_potential:,.2f} (30% recovery rate)")
            
            return OverallInsightsResponse(
                total_practices=len(practices),
                total_claims=total_claims,
                total_denials=total_denials,
                overall_denial_rate=overall_denial_rate,
                total_denied_amount=total_denied_amount,
                top_carc_codes=top_carcs,
                top_payers=top_payers,
                top_cpt_codes=top_cpts,
                key_findings=key_findings,
            )
            
        finally:
            await repository.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in overall insights", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
