"""Overall (system-wide) analytics endpoint."""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Depends, Query
import structlog

from src.api.routes.predictions import get_predictor
from src.api.schemas import OverallInsightsResponse
from src.data_access.factory import get_repository
from src.models.denial_predictor.predictor import DenialPredictor
from src.services.analytics_service import (
    get_practice_data,
    get_payer_performance,
    get_cpt_performance,
)
from src.services.denial_analysis_service import get_carc_rarc_analysis
from src.utils.constants import COMMON_CARC_CODES

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overall-insights", response_model=OverallInsightsResponse)
async def get_overall_insights(
    days_back: int = Query(default=365, ge=1, le=3650),
    predictor: DenialPredictor = Depends(get_predictor),
) -> OverallInsightsResponse:
    """Aggregated insights across all practices."""
    repository = get_repository()
    try:
        practices = await repository.get_practices()

        total_claims = 0
        total_denials = 0
        total_denied_amount = 0.0

        carc_agg: dict = defaultdict(lambda: {"count": 0, "amount": 0.0})
        payer_agg: dict = defaultdict(lambda: {"claims": 0, "denials": 0, "amount": 0.0})
        cpt_agg: dict = defaultdict(lambda: {"claims": 0, "denials": 0, "amount": 0.0})

        for practice in practices:
            try:
                data = await get_practice_data(
                    practice.practice_id, days_back, repository, predictor,
                )
                if data.empty:
                    continue

                total_claims += len(data)
                denied_count = int(data["is_denied"].sum())
                total_denials += denied_count
                denied_amt = float(data[data["is_denied"]]["total_billed_amount"].sum())
                total_denied_amount += denied_amt

                carc_rarc = await get_carc_rarc_analysis(
                    practice.practice_id, days_back, repository,
                )
                for carc in carc_rarc.get("carc_codes", [])[:10]:
                    carc_agg[carc["carc_code"]]["count"] += carc["occurrence_count"]
                    carc_agg[carc["carc_code"]]["amount"] += carc["total_adjustment_amount"]

                for p in get_payer_performance(data)[:10]:
                    payer_agg[p["payer_name"]]["claims"] += p["total_claims"]
                    payer_agg[p["payer_name"]]["denials"] += p["denied_claims"]
                    payer_agg[p["payer_name"]]["amount"] += p["denied_amount"]

                for c in get_cpt_performance(data)[:10]:
                    cpt_agg[c["cpt_code"]]["claims"] += c["total_claims"]
                    cpt_agg[c["cpt_code"]]["denials"] += c["denied_claims"]
                    cpt_agg[c["cpt_code"]]["amount"] += c["denied_amount"]

            except Exception as e:
                logger.warning(f"Error processing practice {practice.practice_id}: {e}")

        overall_denial_rate = total_denials / total_claims if total_claims else 0.0

        top_carcs = sorted(
            [
                {"carc_code": code, "occurrence_count": d["count"], "total_amount": d["amount"]}
                for code, d in carc_agg.items()
            ],
            key=lambda x: x["total_amount"],
            reverse=True,
        )[:10]

        top_payers = sorted(
            [
                {
                    "payer_name": name,
                    "total_claims": d["claims"],
                    "denied_claims": d["denials"],
                    "denial_rate": d["denials"] / d["claims"] if d["claims"] else 0.0,
                    "denied_amount": d["amount"],
                }
                for name, d in payer_agg.items()
            ],
            key=lambda x: x["denied_amount"],
            reverse=True,
        )[:10]

        top_cpts = sorted(
            [
                {
                    "cpt_code": code,
                    "total_claims": d["claims"],
                    "denied_claims": d["denials"],
                    "denial_rate": d["denials"] / d["claims"] if d["claims"] else 0.0,
                    "denied_amount": d["amount"],
                }
                for code, d in cpt_agg.items()
            ],
            key=lambda x: x["denied_amount"],
            reverse=True,
        )[:10]

        # Key findings
        findings: list[str] = []
        if overall_denial_rate > 0.5:
            findings.append(f"Overall denial rate is very high ({overall_denial_rate:.1%})")
        if top_carcs:
            tc = top_carcs[0]
            desc = COMMON_CARC_CODES.get(tc["carc_code"], f"CARC {tc['carc_code']}")
            findings.append(f"Top denial reason: {desc} (${tc['total_amount']:,.2f})")
        if top_payers:
            tp = top_payers[0]
            findings.append(
                f"Top payer by denial amount: {tp['payer_name']} (${tp['denied_amount']:,.2f})"
            )
        if total_denied_amount > 0:
            recovery = total_denied_amount * 0.3
            findings.append(
                f"Potential recovery through appeals: ${recovery:,.2f} (30% recovery rate)"
            )

        return OverallInsightsResponse(
            total_practices=len(practices),
            total_claims=total_claims,
            total_denials=total_denials,
            overall_denial_rate=overall_denial_rate,
            total_denied_amount=total_denied_amount,
            top_carc_codes=top_carcs,
            top_payers=top_payers,
            top_cpt_codes=top_cpts,
            key_findings=findings,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in overall insights", error=str(e))
        raise HTTPException(500, f"Analysis failed: {e}")
    finally:
        await repository.close()

