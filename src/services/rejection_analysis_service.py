"""Rejection analysis service — claim content issues that cause rejections.

Handles:
- Detecting missing/invalid fields in claims and line items
- Computing rejection risk scores per CPT code
"""

from datetime import date, timedelta
from collections import defaultdict
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.data_access.models import ClaimStatus

logger = structlog.get_logger()


def _extract_primary_cpt(raw: str | None) -> str | None:
    """Extract the procedure code from a raw CPT string like ``HC:92507:GN``."""
    if not raw:
        return None
    if ":" in raw:
        parts = raw.split(":")
        return parts[1] if len(parts) > 1 else raw
    return raw


def _is_valid_cpt_hcpcs(cpt: str) -> bool:
    """Check whether a CPT/HCPCS code looks valid."""
    if len(cpt) >= 5:
        if cpt[:5].isdigit():
            return True
        if len(cpt) == 5 and cpt[0].isalpha() and cpt[1:5].isdigit():
            return True  # HCPCS Level II  e.g. G0283
        if len(cpt) == 5 and cpt[:4].isdigit() and cpt[4].isalpha():
            return True  # Proprietary lab  e.g. 0433U
    if len(cpt) == 4 and cpt.isdigit():
        return True
    return False


async def get_rejection_pattern_analysis(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
) -> dict:
    """Identify rejection patterns per CPT code.

    Returns:
        ``{'rejection_patterns': [...]}``
    """
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)

    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )
    if not claims:
        return {"rejection_patterns": []}

    cpt_patterns: dict = defaultdict(lambda: {
        "cpt_code": None,
        "missing_patient_id": 0,
        "missing_provider_id": 0,
        "missing_service_date": 0,
        "missing_submitted_date": 0,
        "invalid_date_order": 0,
        "missing_cpt_in_line_items": 0,
        "invalid_cpt_count": 0,
        "missing_billed_amount": 0,
        "missing_line_items": 0,
        "total_rejections": 0,
        "total_claims": 0,
        "rejection_rate": 0.0,
    })

    # First pass — only actual rejections
    for claim in claims:
        if claim.status != ClaimStatus.REJECTED:
            continue

        line_items = await repository.get_claim_line_items(claim.claim_id)
        primary_cpt = _extract_primary_cpt(line_items[0].cpt_code if line_items else None)
        if not primary_cpt:
            continue

        if cpt_patterns[primary_cpt]["cpt_code"] is None:
            cpt_patterns[primary_cpt]["cpt_code"] = primary_cpt
        cpt_patterns[primary_cpt]["total_rejections"] += 1

        # Field-level checks
        if not claim.patient_id or claim.patient_id == "":
            cpt_patterns[primary_cpt]["missing_patient_id"] += 1
        if not claim.provider_id or claim.provider_id == "":
            cpt_patterns[primary_cpt]["missing_provider_id"] += 1
        if not claim.service_date_from:
            cpt_patterns[primary_cpt]["missing_service_date"] += 1
        if not claim.submitted_date:
            cpt_patterns[primary_cpt]["missing_submitted_date"] += 1
        if claim.service_date_from and claim.submitted_date:
            if claim.submitted_date < claim.service_date_from:
                cpt_patterns[primary_cpt]["invalid_date_order"] += 1
        if not line_items:
            cpt_patterns[primary_cpt]["missing_line_items"] += 1

        missing_cpt_count = sum(1 for li in line_items if not li.cpt_code or li.cpt_code == "")
        if missing_cpt_count > 0:
            cpt_patterns[primary_cpt]["missing_cpt_in_line_items"] += missing_cpt_count

        invalid_cpt_count = 0
        for li in line_items:
            if li.cpt_code:
                cpt = _extract_primary_cpt(li.cpt_code) or ""
                if cpt and not _is_valid_cpt_hcpcs(cpt):
                    invalid_cpt_count += 1
        if invalid_cpt_count > 0:
            cpt_patterns[primary_cpt]["invalid_cpt_count"] += invalid_cpt_count

        if not claim.total_billed_amount or float(claim.total_billed_amount) == 0:
            cpt_patterns[primary_cpt]["missing_billed_amount"] += 1

    # Second pass — count total claims per CPT for rate calculation
    cpt_total: dict[str, int] = defaultdict(int)
    for claim in claims:
        line_items = await repository.get_claim_line_items(claim.claim_id)
        primary_cpt = _extract_primary_cpt(line_items[0].cpt_code if line_items else None)
        if primary_cpt:
            cpt_total[primary_cpt] += 1

    # Build results
    results = []
    for cpt_code, pat in cpt_patterns.items():
        total_for_cpt = cpt_total.get(cpt_code, 0)
        rejection_rate = pat["total_rejections"] / total_for_cpt if total_for_cpt > 0 else 0.0
        risk_score = (
            pat["missing_patient_id"] * 3
            + pat["missing_provider_id"] * 3
            + pat["missing_service_date"] * 3
            + pat["missing_submitted_date"] * 4
            + pat["invalid_date_order"] * 3
            + pat["missing_cpt_in_line_items"] * 2
            + pat["invalid_cpt_count"] * 2
            + pat["missing_billed_amount"] * 2
            + pat["missing_line_items"] * 5
        )
        results.append({
            "cpt_code": cpt_code,
            "total_rejections": pat["total_rejections"],
            "total_claims": total_for_cpt,
            "rejection_rate": rejection_rate,
            "missing_patient_id": pat["missing_patient_id"],
            "missing_provider_id": pat["missing_provider_id"],
            "missing_service_date": pat["missing_service_date"],
            "missing_submitted_date": pat["missing_submitted_date"],
            "invalid_date_order": pat["invalid_date_order"],
            "missing_cpt_in_line_items": pat["missing_cpt_in_line_items"],
            "invalid_cpt_count": pat["invalid_cpt_count"],
            "missing_billed_amount": pat["missing_billed_amount"],
            "missing_line_items": pat["missing_line_items"],
            "rejection_risk_score": risk_score,
        })

    results.sort(key=lambda x: x["rejection_risk_score"], reverse=True)
    return {"rejection_patterns": results}

