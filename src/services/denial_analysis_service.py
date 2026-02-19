"""Denial analysis service — CARC/RARC and CPT-CARC correlation analysis.

Handles:
- Aggregating CARC/RARC codes and their financial impact
- Correlating CPT codes with denial reason codes
"""

from datetime import date, timedelta
from collections import defaultdict
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.utils.constants import COMMON_CARC_CODES

logger = structlog.get_logger()


def _get_carc_description(carc_code: int) -> str:
    """Return a human-readable description for a CARC code."""
    if carc_code in COMMON_CARC_CODES:
        return COMMON_CARC_CODES[carc_code]
    if carc_code in [1, 2, 3]:
        return "Patient Responsibility (Deductible/Coinsurance/Copay)"
    if carc_code in [4, 5, 6, 11, 16, 18]:
        return "Coding Error"
    if carc_code in [50, 54, 55, 56, 57, 58, 59]:
        return "Medical Necessity"
    if carc_code in [22, 23, 24, 25, 26]:
        return "Coordination of Benefits"
    if carc_code in [29, 95]:
        return "Timely Filing"
    return f"CARC {carc_code}"


async def get_carc_rarc_analysis(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
) -> dict:
    """Aggregate CARC/RARC codes and their financial impact for a practice.

    Returns:
        ``{'carc_codes': [...], 'rarc_codes': [...]}``
    """
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)

    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )
    if not claims:
        return {"carc_codes": [], "rarc_codes": []}

    carc_stats: dict = defaultdict(lambda: {"count": 0, "total_amount": 0.0, "claims": set()})
    rarc_stats: dict = defaultdict(lambda: {"count": 0, "total_amount": 0.0, "claims": set()})

    for claim in claims:
        denial_details = await repository.get_denial_details(claim.claim_id)
        for detail in denial_details:
            adj = float(detail.adjustment_amount) if detail.adjustment_amount else 0.0
            if detail.carc_code:
                carc_stats[detail.carc_code]["count"] += 1
                carc_stats[detail.carc_code]["claims"].add(claim.claim_id)
                carc_stats[detail.carc_code]["total_amount"] += adj
            if detail.rarc_code:
                rarc_stats[detail.rarc_code]["count"] += 1
                rarc_stats[detail.rarc_code]["claims"].add(claim.claim_id)
                rarc_stats[detail.rarc_code]["total_amount"] += adj

    carc_results = sorted(
        [
            {
                "carc_code": int(code),
                "occurrence_count": s["count"],
                "affected_claims": len(s["claims"]),
                "total_adjustment_amount": float(s["total_amount"]),
                "description": _get_carc_description(code),
            }
            for code, s in carc_stats.items()
        ],
        key=lambda x: x["total_adjustment_amount"],
        reverse=True,
    )

    rarc_results = sorted(
        [
            {
                "rarc_code": str(code),
                "occurrence_count": s["count"],
                "affected_claims": len(s["claims"]),
                "total_adjustment_amount": float(s["total_amount"]),
            }
            for code, s in rarc_stats.items()
        ],
        key=lambda x: x["total_adjustment_amount"],
        reverse=True,
    )

    return {"carc_codes": carc_results, "rarc_codes": rarc_results}


def _extract_cpt_from_code(raw: str | None) -> str | None:
    """Extract the procedure code from a raw CPT string like ``HC:92507:GN``."""
    if not raw:
        return None
    if ":" in raw:
        parts = raw.split(":")
        return parts[1] if len(parts) > 1 else raw
    return raw


async def get_cpt_carc_correlation(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
) -> dict:
    """Correlate CPT codes with CARC/RARC denial reasons.

    Returns:
        ``{'cpt_carc': [...], 'cpt_rarc': [...]}``
    """
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)

    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )
    if not claims:
        return {"cpt_carc": [], "cpt_rarc": []}

    cpt_carc: dict = defaultdict(
        lambda: {"count": 0, "total_amount": 0.0, "claims": set()}
    )
    cpt_rarc: dict = defaultdict(
        lambda: {"count": 0, "total_amount": 0.0, "claims": set()}
    )

    for claim in claims:
        line_items = await repository.get_claim_line_items(claim.claim_id)
        line_cpt = {li.line_item_id: _extract_cpt_from_code(li.cpt_code) for li in line_items}

        denial_details = await repository.get_denial_details(claim.claim_id)
        for detail in denial_details:
            cpt_code = (
                line_cpt.get(detail.line_item_id)
                if detail.line_item_id
                else None
            )
            if not cpt_code and line_items:
                cpt_code = _extract_cpt_from_code(line_items[0].cpt_code)
            if not cpt_code:
                continue

            adj = float(detail.adjustment_amount) if detail.adjustment_amount else 0.0

            if detail.carc_code:
                key = (cpt_code, detail.carc_code)
                cpt_carc[key]["count"] += 1
                cpt_carc[key]["claims"].add(claim.claim_id)
                cpt_carc[key]["total_amount"] += adj

            if detail.rarc_code:
                key = (cpt_code, detail.rarc_code)
                cpt_rarc[key]["count"] += 1
                cpt_rarc[key]["claims"].add(claim.claim_id)
                cpt_rarc[key]["total_amount"] += adj

    cpt_carc_results = sorted(
        [
            {
                "cpt_code": str(k[0]),
                "carc_code": int(k[1]),
                "occurrence_count": v["count"],
                "affected_claims": len(v["claims"]),
                "total_adjustment_amount": float(v["total_amount"]),
                "carc_description": _get_carc_description(k[1]),
            }
            for k, v in cpt_carc.items()
        ],
        key=lambda x: x["total_adjustment_amount"],
        reverse=True,
    )

    cpt_rarc_results = sorted(
        [
            {
                "cpt_code": str(k[0]),
                "rarc_code": str(k[1]),
                "occurrence_count": v["count"],
                "affected_claims": len(v["claims"]),
                "total_adjustment_amount": float(v["total_amount"]),
            }
            for k, v in cpt_rarc.items()
        ],
        key=lambda x: x["total_adjustment_amount"],
        reverse=True,
    )

    return {"cpt_carc": cpt_carc_results, "cpt_rarc": cpt_rarc_results}

