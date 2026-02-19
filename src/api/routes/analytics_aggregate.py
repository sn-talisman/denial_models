"""Aggregate analytics endpoints — practices, payers, and combos."""

from fastapi import APIRouter, HTTPException, Depends, Query
import pandas as pd
import structlog

from src.api.routes.predictions import get_predictor
from src.api.schemas import (
    PracticeAnalysisResponse,
    PayerAnalysisResponse,
    PracticePayerComboResponse,
)
from src.data_access.factory import get_repository
from src.models.denial_predictor.predictor import DenialPredictor
from src.services.analytics_service import (
    run_aggregate_prediction_pipeline,
    aggregate_by_group,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/practices", response_model=list[PracticeAnalysisResponse])
async def analyze_practices(
    days_back: int = Query(default=365, ge=1, le=3650),
    min_claims: int = Query(default=5, ge=1),
    predictor: DenialPredictor = Depends(get_predictor),
) -> list[PracticeAnalysisResponse]:
    """Analyze denial and rejection rates by practice."""
    repository = get_repository()
    try:
        df = await run_aggregate_prediction_pipeline(days_back, repository, predictor)
        if df.empty:
            return []

        rows = aggregate_by_group(df, "practice_id", "practice_name", min_claims)
        return [
            PracticeAnalysisResponse(
                practice_id=r["id"],
                practice_name=r["name"],
                **{k: v for k, v in r.items() if k not in ("id", "name")},
            )
            for r in rows
        ]
    except Exception as e:
        logger.error("Error in practice analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        await repository.close()


@router.get("/payers", response_model=list[PayerAnalysisResponse])
async def analyze_payers(
    days_back: int = Query(default=365, ge=1, le=3650),
    min_claims: int = Query(default=5, ge=1),
    predictor: DenialPredictor = Depends(get_predictor),
) -> list[PayerAnalysisResponse]:
    """Analyze denial and rejection rates by payer."""
    repository = get_repository()
    try:
        df = await run_aggregate_prediction_pipeline(days_back, repository, predictor)
        if df.empty:
            return []

        rows = aggregate_by_group(df, "payer_id", "payer_name", min_claims)
        return [
            PayerAnalysisResponse(
                payer_id=r["id"],
                payer_name=r["name"],
                **{k: v for k, v in r.items() if k not in ("id", "name")},
            )
            for r in rows
        ]
    except Exception as e:
        logger.error("Error in payer analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        await repository.close()


@router.get("/practice-payer", response_model=list[PracticePayerComboResponse])
async def analyze_practice_payer_combos(
    days_back: int = Query(default=365, ge=1, le=3650),
    min_claims: int = Query(default=5, ge=1),
    predictor: DenialPredictor = Depends(get_predictor),
) -> list[PracticePayerComboResponse]:
    """Analyze denial and rejection rates by practice-payer combination."""
    repository = get_repository()
    try:
        df = await run_aggregate_prediction_pipeline(days_back, repository, predictor)
        if df.empty:
            return []

        results: list[PracticePayerComboResponse] = []
        for (practice_id, payer_id), combo in df.groupby(["practice_id", "payer_id"]):
            if pd.isna(practice_id) or pd.isna(payer_id) or len(combo) < min_claims:
                continue

            practice_name_val = combo["practice_name"].iloc[0]
            practice_name = str(practice_name_val) if pd.notna(practice_name_val) else "Unknown"
            payer_name_val = combo["payer_name"].iloc[0]
            payer_name = str(payer_name_val) if pd.notna(payer_name_val) else "Unknown"

            total = len(combo)
            denied = int(combo["is_denied"].sum())
            rejected = int(combo["is_rejected"].sum())
            denied_or_rejected = int((combo["is_denied"] | combo["is_rejected"]).sum())
            high_risk = int((combo["risk_level"] == "high").sum())
            avg_prob = float(combo["denial_probability"].mean())
            total_billed = float(combo["total_billed_amount"].sum())
            denied_billed = float(combo[combo["is_denied"]]["total_billed_amount"].sum())

            results.append(PracticePayerComboResponse(
                practice_id=str(practice_id),
                practice_name=practice_name,
                payer_id=str(payer_id),
                payer_name=payer_name,
                total_claims=total,
                denied_claims=denied,
                rejected_claims=rejected,
                denied_or_rejected=denied_or_rejected,
                denial_rate=denied / total if total else 0.0,
                rejection_rate=rejected / total if total else 0.0,
                denial_or_rejection_rate=denied_or_rejected / total if total else 0.0,
                avg_denial_probability=avg_prob,
                high_risk_count=high_risk,
                high_risk_pct=high_risk / total if total else 0.0,
                total_billed=total_billed,
                denied_billed=denied_billed,
                denied_billed_pct=denied_billed / total_billed if total_billed else 0.0,
            ))

        results.sort(key=lambda x: x.denial_rate, reverse=True)
        return results

    except Exception as e:
        logger.error("Error in practice-payer analysis", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
    finally:
        await repository.close()

