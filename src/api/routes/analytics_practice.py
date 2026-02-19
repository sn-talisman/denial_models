"""Practice-specific analytics endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Query
import pandas as pd
import structlog

from src.api.routes.predictions import get_predictor
from src.api.schemas import (
    PerformanceInsights,
    PerformanceSummaryResponse,
    ActionItemResponse,
    PrioritizedActionItemsResponse,
    PayerPerformanceItem,
    PayerPerformanceResponse,
    CPTPerformanceItem,
    CPTPerformanceResponse,
    HighRiskClaimItem,
    HighRiskClaimsResponse,
    CARCCodeItem,
    RARCCodeItem,
    CARCRARCAnalysisResponse,
    CPTCARCCorrelationItem,
    CPTRARCCorrelationItem,
    CPTCARCCorrelationResponse,
    RejectionPatternItem,
    RejectionPatternResponse,
)
from src.data_access.factory import get_repository
from src.models.denial_predictor.predictor import DenialPredictor
from src.services.analytics_service import (
    get_practice_data,
    calculate_performance_summary,
    get_prioritized_action_items,
    get_payer_performance,
    get_cpt_performance,
    get_high_risk_claims,
)
from src.services.denial_analysis_service import (
    get_carc_rarc_analysis,
    get_cpt_carc_correlation,
)
from src.services.rejection_analysis_service import (
    get_rejection_pattern_analysis,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# ── Helpers ─────────────────────────────────────────────────────────────────

async def _resolve_practice_name(repository, practice_guid: str) -> str:
    """Resolve a practice GUID to its display name."""
    practices = await repository.get_practices()
    practice_map = {p.practice_id: p.name for p in practices}
    name = practice_map.get(practice_guid, "Unknown")
    return str(name) if pd.notna(name) else "Unknown"


# ── Performance Summary ─────────────────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/performance-summary",
    response_model=PerformanceSummaryResponse,
)
async def get_performance_summary(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
    predictor: DenialPredictor = Depends(get_predictor),
) -> PerformanceSummaryResponse:
    """Get performance summary for a specific practice."""
    repository = get_repository()
    try:
        data = await get_practice_data(practice_guid, days_back, repository, predictor)
        if data.empty:
            raise HTTPException(404, f"No claims found for practice {practice_guid}")

        overall_denial_rate = 0.24
        overall_avg_prob = 0.10
        summary = calculate_performance_summary(data, overall_denial_rate, overall_avg_prob)

        practice_name = data["practice_name"].iloc[0] if len(data) else "Unknown"
        insights_dict = summary.pop("insights", {})

        return PerformanceSummaryResponse(
            practice_id=practice_guid,
            practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
            insights=PerformanceInsights(**insights_dict),
            **summary,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in performance summary", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()


# ── Action Items ────────────────────────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/action-items",
    response_model=PrioritizedActionItemsResponse,
)
async def get_action_items(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
    predictor: DenialPredictor = Depends(get_predictor),
) -> PrioritizedActionItemsResponse:
    """Get prioritized action items for a specific practice."""
    repository = get_repository()
    try:
        data = await get_practice_data(practice_guid, days_back, repository, predictor)
        if data.empty:
            raise HTTPException(404, f"No claims found for practice {practice_guid}")

        carc_rarc_data = await get_carc_rarc_analysis(practice_guid, days_back, repository)
        cpt_carc_data = await get_cpt_carc_correlation(practice_guid, days_back, repository)

        items = get_prioritized_action_items(
            data, carc_rarc_data=carc_rarc_data, cpt_carc_data=cpt_carc_data,
        )
        practice_name = data["practice_name"].iloc[0] if len(data) else "Unknown"

        return PrioritizedActionItemsResponse(
            practice_id=practice_guid,
            practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
            action_items=[ActionItemResponse(**i) for i in items],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in action items", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()


# ── Payer Performance ───────────────────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/payer-performance",
    response_model=PayerPerformanceResponse,
)
async def get_practice_payer_performance(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
    predictor: DenialPredictor = Depends(get_predictor),
) -> PayerPerformanceResponse:
    """Get payer performance breakdown for a specific practice."""
    repository = get_repository()
    try:
        data = await get_practice_data(practice_guid, days_back, repository, predictor)
        if data.empty:
            raise HTTPException(404, f"No claims found for practice {practice_guid}")

        payer_perf = get_payer_performance(data)
        practice_name = data["practice_name"].iloc[0] if len(data) else "Unknown"

        return PayerPerformanceResponse(
            practice_id=practice_guid,
            practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
            payers=[PayerPerformanceItem(**p) for p in payer_perf],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in payer performance", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()


# ── CPT Performance ─────────────────────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/cpt-performance",
    response_model=CPTPerformanceResponse,
)
async def get_practice_cpt_performance(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
    predictor: DenialPredictor = Depends(get_predictor),
) -> CPTPerformanceResponse:
    """Get CPT code performance breakdown for a specific practice."""
    repository = get_repository()
    try:
        data = await get_practice_data(practice_guid, days_back, repository, predictor)
        if data.empty:
            raise HTTPException(404, f"No claims found for practice {practice_guid}")

        cpt_perf = get_cpt_performance(data)
        practice_name = data["practice_name"].iloc[0] if len(data) else "Unknown"

        return CPTPerformanceResponse(
            practice_id=practice_guid,
            practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
            cpt_codes=[CPTPerformanceItem(**c) for c in cpt_perf],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in CPT performance", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()


# ── High-Risk Claims ────────────────────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/high-risk-claims",
    response_model=HighRiskClaimsResponse,
)
async def get_practice_high_risk_claims(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
    limit: int = Query(default=20, ge=1, le=100),
    predictor: DenialPredictor = Depends(get_predictor),
) -> HighRiskClaimsResponse:
    """Get high-risk claims for a specific practice."""
    repository = get_repository()
    try:
        data = await get_practice_data(practice_guid, days_back, repository, predictor)
        if data.empty:
            raise HTTPException(404, f"No claims found for practice {practice_guid}")

        high_risk = get_high_risk_claims(data, limit=limit)
        practice_name = data["practice_name"].iloc[0] if len(data) else "Unknown"

        return HighRiskClaimsResponse(
            practice_id=practice_guid,
            practice_name=str(practice_name) if pd.notna(practice_name) else "Unknown",
            high_risk_claims=[HighRiskClaimItem(**h) for h in high_risk],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in high-risk claims", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()


# ── Denial Reasons (CARC / RARC) ───────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/denial-reasons",
    response_model=CARCRARCAnalysisResponse,
)
async def get_denial_reasons(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
) -> CARCRARCAnalysisResponse:
    """Get CARC/RARC code analysis for a specific practice."""
    repository = get_repository()
    try:
        analysis = await get_carc_rarc_analysis(practice_guid, days_back, repository)
        practice_name = await _resolve_practice_name(repository, practice_guid)

        return CARCRARCAnalysisResponse(
            practice_id=practice_guid,
            practice_name=practice_name,
            carc_codes=[CARCCodeItem(**c) for c in analysis["carc_codes"]],
            rarc_codes=[RARCCodeItem(**r) for r in analysis["rarc_codes"]],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in denial reasons", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()


# ── CPT-CARC Correlation ───────────────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/cpt-carc-correlation",
    response_model=CPTCARCCorrelationResponse,
)
async def get_cpt_carc_correlation_endpoint(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
) -> CPTCARCCorrelationResponse:
    """Get CPT-CARC/RARC correlation analysis for a specific practice."""
    repository = get_repository()
    try:
        correlation = await get_cpt_carc_correlation(practice_guid, days_back, repository)
        practice_name = await _resolve_practice_name(repository, practice_guid)

        return CPTCARCCorrelationResponse(
            practice_id=practice_guid,
            practice_name=practice_name,
            cpt_carc=[CPTCARCCorrelationItem(**c) for c in correlation["cpt_carc"]],
            cpt_rarc=[CPTRARCCorrelationItem(**r) for r in correlation["cpt_rarc"]],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in CPT-CARC correlation", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()


# ── Rejection Patterns ──────────────────────────────────────────────────────

@router.get(
    "/practice/{practice_guid}/rejection-patterns",
    response_model=RejectionPatternResponse,
)
async def get_rejection_patterns(
    practice_guid: str,
    days_back: int = Query(default=365, ge=1, le=3650),
) -> RejectionPatternResponse:
    """Get rejection pattern analysis for a specific practice."""
    repository = get_repository()
    try:
        analysis = await get_rejection_pattern_analysis(practice_guid, days_back, repository)
        practice_name = await _resolve_practice_name(repository, practice_guid)

        return RejectionPatternResponse(
            practice_id=practice_guid,
            practice_name=practice_name,
            rejection_patterns=[RejectionPatternItem(**p) for p in analysis["rejection_patterns"]],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in rejection patterns", error=str(e), practice_guid=practice_guid)
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()

