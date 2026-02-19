"""Core analytics service for practice-level data retrieval and analysis.

Handles:
- Fetching and enriching practice data with predictions
- Aggregate (all-practices / all-payers) analysis pipelines
- Performance summary calculations
- Payer and CPT code performance breakdowns
- High-risk claim identification
- Prioritized action item generation
"""

from typing import Optional
from datetime import date, timedelta
import pandas as pd
import numpy as np
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.models.denial_predictor.predictor import DenialPredictor

logger = structlog.get_logger()


# ── Data Retrieval ──────────────────────────────────────────────────────────

async def get_practice_data(
    practice_id: str,
    days_back: int,
    repository: ClaimsRepository,
    predictor: DenialPredictor,
) -> pd.DataFrame:
    """Fetch claims for a practice, engineer features, and make predictions.

    Args:
        practice_id: Practice GUID
        days_back: Number of days to look back
        repository: Database repository
        predictor: Denial predictor instance

    Returns:
        DataFrame with claims, features, and predictions
    """
    from src.pipelines.feature_engineering.feature_engineer_optimized import (
        engineer_features_batch_optimized,
    )

    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)

    claims = await repository.get_claims(
        practice_id=practice_id,
        date_from=date_from,
        date_to=date_to,
    )

    if not claims:
        return pd.DataFrame()

    df = await engineer_features_batch_optimized(
        claims=claims,
        repository=repository,
        reference_date=date_to,
    )

    if df.empty:
        return pd.DataFrame()

    # Prepare feature matrix for prediction
    exclude_cols = [
        "claim_id", "claim_number", "service_date", "submitted_date",
        "adjudicated_date", "primary_cpt_code", "claim_status",
        "cpt_code", "cpt_category", "is_denied",
    ]
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    features_df = df[feature_cols].copy()

    for col in features_df.columns:
        if features_df[col].dtype == "object":
            try:
                features_df[col] = pd.to_numeric(features_df[col], errors="coerce")
            except Exception:
                pass

    features_df = features_df.fillna(0)
    for col in features_df.columns:
        if features_df[col].dtype == "object":
            features_df[col] = features_df[col].astype(float)

    predictions_df = predictor.predict_batch(features_df)

    # Enrich with claim metadata
    claim_map = {
        "practice_id": {c.claim_id: c.practice_id for c in claims},
        "payer_id": {c.claim_id: c.payer_id for c in claims},
        "provider_id": {c.claim_id: c.provider_id for c in claims},
        "service_date": {c.claim_id: c.service_date_from for c in claims},
        "submitted_date": {c.claim_id: c.submitted_date for c in claims},
    }

    predictions_df["claim_id"] = df["claim_id"].values
    for col_name, mapping in claim_map.items():
        predictions_df[col_name] = predictions_df["claim_id"].map(mapping)

    # Carry over engineered columns
    carry_cols = {
        "is_denied": False,
        "total_billed_amount": 0,
        "total_paid_amount": 0,
        "payment_ratio": 0,
        "has_partial_denial": False,
        "adjustment_ratio": 0,
        "primary_cpt_code": "",
    }
    for col_name, default in carry_cols.items():
        if col_name in df.columns:
            predictions_df[col_name] = df[col_name].values
        else:
            predictions_df[col_name] = [default] * len(df)

    # Resolve practice and payer names
    practices = await repository.get_practices()
    payers = await repository.get_payers()
    practice_map = {p.practice_id: p.name for p in practices}
    payer_map = {p.payer_id: p.name for p in payers}

    predictions_df["practice_name"] = predictions_df["practice_id"].map(practice_map)
    predictions_df["payer_name"] = predictions_df["payer_id"].map(payer_map)

    # Fill missing names with short GUID fallback
    for col, prefix in [("practice_name", "Practice "), ("payer_name", "Payer ")]:
        id_col = col.replace("_name", "_id")
        missing = predictions_df[col].isna() & predictions_df[id_col].notna()
        predictions_df.loc[missing, col] = (
            prefix + predictions_df.loc[missing, id_col].astype(str).str[:20]
        )

    return predictions_df


# ── Performance Summary ─────────────────────────────────────────────────────

def get_performance_insights(practice_data: pd.DataFrame) -> dict:
    """Compute trends, risk factors, and key issues for a practice."""
    insights: dict = {
        "trends": {},
        "comparisons": {},
        "key_issues": [],
        "risk_factors": [],
    }

    total = len(practice_data)
    if total == 0:
        return insights

    denied = practice_data["is_denied"].sum()
    denied_rate = denied / total if total > 0 else 0

    # Daily denial trends
    if "service_date" in practice_data.columns:
        daily = practice_data[practice_data["service_date"].notna()].copy()
        if not daily.empty:
            stats = daily.groupby("service_date").agg({"is_denied": ["sum", "count"]})
            stats.columns = ["denied_count", "total_count"]
            stats["denial_rate"] = stats["denied_count"] / stats["total_count"]
            stats = stats.sort_index()
            insights["trends"] = {
                str(d): float(r["denial_rate"]) for d, r in stats.iterrows()
            }

    # High-risk payers
    if "payer_name" in practice_data.columns:
        pr = practice_data.groupby("payer_name").agg({"is_denied": ["sum", "count"]})
        pr.columns = ["denied", "total"]
        pr["rate"] = pr["denied"] / pr["total"]
        for payer in pr[pr["rate"] > 0.5].index.tolist()[:5]:
            insights["risk_factors"].append(f"High denial rate with {payer}")

    # High-risk CPT codes
    if "primary_cpt_code" in practice_data.columns:
        cr = practice_data.groupby("primary_cpt_code").agg({"is_denied": ["sum", "count"]})
        cr.columns = ["denied", "total"]
        cr["rate"] = cr["denied"] / cr["total"]
        for cpt in cr[cr["rate"] > 0.5].index.tolist()[:5]:
            insights["risk_factors"].append(f"High denial rate for CPT {cpt}")

    # Key issues
    if denied_rate > 0.5:
        insights["key_issues"].append(f"Very high denial rate ({denied_rate:.1%}) - above 50%")
    elif denied_rate > 0.3:
        insights["key_issues"].append(f"High denial rate ({denied_rate:.1%}) - above 30%")

    if "risk_level" in practice_data.columns:
        high_pct = (practice_data["risk_level"] == "high").sum() / total
        if high_pct > 0.5:
            insights["key_issues"].append(
                f"High percentage of high-risk claims ({high_pct:.1%})"
            )

    return insights


def calculate_performance_summary(
    practice_data: pd.DataFrame,
    overall_denial_rate: float,
    overall_avg_prob: float,
) -> dict:
    """Calculate performance summary for a practice."""
    total = len(practice_data)
    denied = practice_data["is_denied"].sum()
    denied_rate = denied / total if total > 0 else 0

    total_billed = practice_data["total_billed_amount"].sum()
    total_paid = practice_data["total_paid_amount"].sum()
    denied_amount = practice_data[practice_data["is_denied"]]["total_billed_amount"].sum()

    avg_probability = practice_data["denial_probability"].mean()
    high_risk = (practice_data["risk_level"] == "high").sum()
    high_risk_pct = high_risk / total if total > 0 else 0

    insights = get_performance_insights(practice_data)
    recovery_potential = denied_amount * 0.3  # 30% assumed recovery rate

    return {
        "total_claims": int(total),
        "denied_claims": int(denied),
        "denial_rate": float(denied_rate),
        "denial_rate_vs_overall": float(denied_rate - overall_denial_rate),
        "total_billed": float(total_billed),
        "total_paid": float(total_paid),
        "denied_amount": float(denied_amount),
        "recovery_potential": float(recovery_potential),
        "avg_denial_probability": float(avg_probability),
        "avg_probability_vs_overall": float(avg_probability - overall_avg_prob),
        "high_risk_claims": int(high_risk),
        "high_risk_pct": float(high_risk_pct),
        "insights": insights,
    }


# ── Payer Performance ───────────────────────────────────────────────────────

def get_payer_performance(practice_data: pd.DataFrame) -> list[dict]:
    """Get aggregated payer performance."""
    summary = (
        practice_data.groupby("payer_name")
        .agg({
            "claim_id": "count",
            "is_denied": "sum",
            "total_billed_amount": "sum",
            "total_paid_amount": "sum",
            "denial_probability": "mean",
        })
        .reset_index()
    )
    summary.columns = [
        "payer_name", "total_claims", "denied", "total_billed", "total_paid", "avg_denial_prob",
    ]
    summary["denial_rate"] = summary["denied"] / summary["total_claims"]

    denied_by_payer = (
        practice_data[practice_data["is_denied"]]
        .groupby("payer_name")["total_billed_amount"]
        .sum()
        .reset_index()
    )
    denied_by_payer.columns = ["payer_name", "denied_amount"]
    summary = summary.merge(denied_by_payer, on="payer_name", how="left")
    summary["denied_amount"] = summary["denied_amount"].fillna(0)
    summary = summary.sort_values("denied_amount", ascending=False)

    return [
        {
            "payer_name": str(row["payer_name"]),
            "total_claims": int(row["total_claims"]),
            "denied_claims": int(row["denied"]),
            "denial_rate": float(row["denial_rate"]),
            "total_billed": float(row["total_billed"]),
            "total_paid": float(row["total_paid"]),
            "denied_amount": float(row["denied_amount"]),
            "avg_denial_probability": float(row["avg_denial_prob"]),
        }
        for _, row in summary.iterrows()
    ]


# ── CPT Performance ─────────────────────────────────────────────────────────

def get_cpt_performance(practice_data: pd.DataFrame) -> list[dict]:
    """Get aggregated CPT code performance."""
    cpt_data = practice_data[
        practice_data["primary_cpt_code"].notna() & (practice_data["primary_cpt_code"] != "")
    ]
    if len(cpt_data) == 0:
        return []

    summary = (
        cpt_data.groupby("primary_cpt_code")
        .agg({
            "claim_id": "count",
            "is_denied": "sum",
            "total_billed_amount": "sum",
            "denial_probability": "mean",
        })
        .reset_index()
    )
    summary.columns = ["cpt_code", "total_claims", "denied", "total_billed", "avg_denial_prob"]
    summary["denial_rate"] = summary["denied"] / summary["total_claims"]

    denied_by_cpt = (
        cpt_data[cpt_data["is_denied"]]
        .groupby("primary_cpt_code")["total_billed_amount"]
        .sum()
        .reset_index()
    )
    denied_by_cpt.columns = ["cpt_code", "denied_amount"]
    summary = summary.merge(denied_by_cpt, on="cpt_code", how="left")
    summary["denied_amount"] = summary["denied_amount"].fillna(0)
    summary = summary.sort_values("denied_amount", ascending=False)

    return [
        {
            "cpt_code": str(row["cpt_code"]),
            "total_claims": int(row["total_claims"]),
            "denied_claims": int(row["denied"]),
            "denial_rate": float(row["denial_rate"]),
            "total_billed": float(row["total_billed"]),
            "denied_amount": float(row["denied_amount"]),
            "avg_denial_probability": float(row["avg_denial_prob"]),
        }
        for _, row in summary.iterrows()
    ]


# ── High-Risk Claims ────────────────────────────────────────────────────────

def get_high_risk_claims(practice_data: pd.DataFrame, limit: int = 20) -> list[dict]:
    """Get high-risk claims requiring immediate attention."""
    high_risk = practice_data[practice_data["risk_level"] == "high"].sort_values(
        "denial_probability", ascending=False
    )

    return [
        {
            "claim_id": str(row["claim_id"]) if pd.notna(row["claim_id"]) else None,
            "payer_name": str(row["payer_name"]) if pd.notna(row["payer_name"]) else "Unknown",
            "cpt_code": str(row["primary_cpt_code"]) if pd.notna(row["primary_cpt_code"]) else None,
            "denial_probability": float(row["denial_probability"]),
            "billed_amount": float(row["total_billed_amount"]),
            "is_denied": bool(row["is_denied"]) if pd.notna(row["is_denied"]) else False,
        }
        for _, row in high_risk.head(limit).iterrows()
    ]


# ── Prioritized Action Items ───────────────────────────────────────────────

def _analyze_payer_patterns(practice_data: pd.DataFrame) -> list[dict]:
    """Identify payer-specific denial patterns for action items."""
    items = []
    for payer_name, payer_data in practice_data.groupby("payer_name"):
        if pd.isna(payer_name) or payer_name == "":
            continue
        total = len(payer_data)
        denied = payer_data["is_denied"].sum()
        denial_rate = denied / total if total > 0 else 0
        denied_amount = payer_data[payer_data["is_denied"]]["total_billed_amount"].sum()
        if total < 3:
            continue
        if denial_rate > 0.5:
            items.append({
                "priority": "HIGH",
                "title": f"High Denial Rate with {str(payer_name)[:40]}",
                "financial_impact": float(denied_amount),
                "recommendation": (
                    f"Review documentation requirements and coding practices for "
                    f"{str(payer_name)[:30]}. Consider payer-specific training for billing staff."
                ),
                "details": f"{denial_rate:.1%} denial rate on {total} claims (${denied_amount:,.2f} at risk)",
                "type": "payer",
                "payer_name": str(payer_name),
            })
    return items


def _analyze_cpt_patterns(practice_data: pd.DataFrame) -> list[dict]:
    """Identify CPT-specific denial patterns for action items."""
    items = []
    cpt_data = practice_data[
        practice_data["primary_cpt_code"].notna() & (practice_data["primary_cpt_code"] != "")
    ]
    for cpt_code, cpt_claims in cpt_data.groupby("primary_cpt_code"):
        total = len(cpt_claims)
        denied = cpt_claims["is_denied"].sum()
        denial_rate = denied / total if total > 0 else 0
        denied_amount = cpt_claims[cpt_claims["is_denied"]]["total_billed_amount"].sum()
        if total < 5 or denial_rate <= 0.4:
            continue
        payer_breakdown = cpt_claims[cpt_claims["is_denied"]].groupby("payer_name")[
            "total_billed_amount"
        ].sum()
        if len(payer_breakdown) > 0:
            top_payer = payer_breakdown.idxmax()
            items.append({
                "priority": "HIGH" if denial_rate > 0.6 else "MEDIUM",
                "title": f"High Denial Rate for CPT {cpt_code}",
                "financial_impact": float(denied_amount),
                "recommendation": (
                    f"Review coding accuracy and documentation for CPT {cpt_code}. "
                    f"Primary issue with {str(top_payer)[:30]}."
                ),
                "details": (
                    f"{denial_rate:.1%} denial rate ({denied}/{total} claims, "
                    f"${denied_amount:,.2f} at risk)"
                ),
                "type": "cpt",
                "cpt_code": str(cpt_code),
            })
    return items


def get_prioritized_action_items(
    practice_data: pd.DataFrame,
    carc_rarc_data: Optional[dict] = None,
    cpt_carc_data: Optional[dict] = None,
) -> list[dict]:
    """Generate prioritized, actionable recommendations sorted by financial impact."""
    action_items: list[dict] = []

    # Payer issues
    for item in _analyze_payer_patterns(practice_data)[:5]:
        action_items.append(item)

    # CPT issues
    for item in _analyze_cpt_patterns(practice_data)[:5]:
        action_items.append(item)

    # CARC-driven insights
    if carc_rarc_data and carc_rarc_data.get("carc_codes"):
        top_carc = carc_rarc_data["carc_codes"][0]
        if top_carc["total_adjustment_amount"] > 1000:
            from src.utils.constants import COMMON_CARC_CODES
            carc_code = top_carc["carc_code"]
            carc_desc = COMMON_CARC_CODES.get(carc_code, f"CARC {carc_code}")
            action_items.append({
                "priority": "high" if top_carc["total_adjustment_amount"] > 10000 else "medium",
                "title": f"Top Denial Reason: {carc_desc} (CARC {carc_code})",
                "financial_impact": float(top_carc["total_adjustment_amount"]),
                "recommendation": f"Review denial reason: {carc_desc}. Investigate root cause.",
                "details": (
                    f"{top_carc['occurrence_count']} occurrences affecting "
                    f"{top_carc['affected_claims']} claims"
                ),
                "type": "carc",
                "carc_code": carc_code,
            })

    # CPT-CARC correlation insights
    if cpt_carc_data and cpt_carc_data.get("cpt_carc"):
        top_combo = cpt_carc_data["cpt_carc"][0]
        if top_combo["total_adjustment_amount"] > 5000:
            from src.utils.constants import COMMON_CARC_CODES
            carc_code = top_combo["carc_code"]
            carc_desc = COMMON_CARC_CODES.get(carc_code, f"CARC {carc_code}")
            action_items.append({
                "priority": "high" if top_combo["total_adjustment_amount"] > 20000 else "medium",
                "title": f"CPT {top_combo['cpt_code']} + {carc_desc} (CARC {carc_code})",
                "financial_impact": float(top_combo["total_adjustment_amount"]),
                "recommendation": (
                    f"Review CPT {top_combo['cpt_code']} billing practices. "
                    f"Frequently denied with {carc_desc}."
                ),
                "details": (
                    f"{top_combo['occurrence_count']} occurrences affecting "
                    f"{top_combo['affected_claims']} claims"
                ),
                "type": "cpt_carc",
                "cpt_code": top_combo["cpt_code"],
                "carc_code": carc_code,
            })

    action_items.sort(key=lambda x: x["financial_impact"], reverse=True)
    return action_items[:15]


# ── Aggregate Prediction Pipeline ───────────────────────────────────────────

async def run_aggregate_prediction_pipeline(
    days_back: int,
    repository: ClaimsRepository,
    predictor: DenialPredictor,
    *,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Fetch all claims, engineer features, and run predictions.

    This is the shared pipeline used by the aggregate analytics endpoints
    (practices, payers, practice-payer combos).

    Returns an enriched DataFrame with predictions, claim metadata, and
    resolved practice/payer names.
    """
    from src.pipelines.feature_engineering.feature_engineer_optimized import (
        engineer_features_batch_optimized,
    )

    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)

    claims = await repository.get_claims(
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    if not claims:
        return pd.DataFrame()

    df = await engineer_features_batch_optimized(
        claims=claims,
        repository=repository,
        reference_date=date_to,
    )
    if df.empty:
        return pd.DataFrame()

    # Prepare feature matrix
    exclude_cols = [
        "claim_id", "claim_number", "service_date", "submitted_date",
        "adjudicated_date", "primary_cpt_code", "claim_status",
        "cpt_code", "cpt_category", "is_denied",
    ]
    feature_cols = [c for c in df.columns if c not in exclude_cols]
    features_df = df[feature_cols].copy()

    for col in features_df.columns:
        if features_df[col].dtype == "object":
            try:
                features_df[col] = pd.to_numeric(features_df[col], errors="coerce")
            except Exception:
                pass
    features_df = features_df.fillna(0)
    for col in features_df.columns:
        if features_df[col].dtype == "object":
            features_df[col] = features_df[col].astype(float)

    predictions_df = predictor.predict_batch(features_df)

    # Enrich with claim metadata
    claim_practice = {c.claim_id: c.practice_id for c in claims}
    claim_payer = {c.claim_id: c.payer_id for c in claims}

    predictions_df["claim_id"] = df["claim_id"].values
    predictions_df["practice_id"] = predictions_df["claim_id"].map(claim_practice)
    predictions_df["payer_id"] = predictions_df["claim_id"].map(claim_payer)
    predictions_df["is_denied"] = (
        df["is_denied"].values if "is_denied" in df.columns else [False] * len(df)
    )
    predictions_df["is_rejected"] = (
        df["is_rejected"].values if "is_rejected" in df.columns else [False] * len(df)
    )
    predictions_df["total_billed_amount"] = (
        df["total_billed_amount"].values
        if "total_billed_amount" in df.columns
        else [0] * len(df)
    )

    # Resolve names
    practices = await repository.get_practices()
    payers = await repository.get_payers()
    practice_map = {p.practice_id: p.name for p in practices}
    payer_map = {p.payer_id: p.name for p in payers}

    predictions_df["practice_name"] = predictions_df["practice_id"].map(practice_map)
    predictions_df["payer_name"] = predictions_df["payer_id"].map(payer_map)

    for col, prefix in [("practice_name", "Practice "), ("payer_name", "Payer ")]:
        id_col = col.replace("_name", "_id")
        missing = predictions_df[col].isna() & predictions_df[id_col].notna()
        predictions_df.loc[missing, col] = (
            prefix + predictions_df.loc[missing, id_col].astype(str).str[:20]
        )

    return predictions_df


def aggregate_by_group(
    predictions_df: pd.DataFrame,
    group_col: str,
    name_col: str,
    min_claims: int = 5,
) -> list[dict]:
    """Aggregate prediction results by a grouping column.

    Returns a list of dicts with standard aggregate metrics suitable for
    PracticeAnalysisResponse / PayerAnalysisResponse.
    """
    results = []
    for group_id in predictions_df[group_col].dropna().unique():
        data = predictions_df[predictions_df[group_col] == group_id]
        if len(data) < min_claims:
            continue

        name_val = data[name_col].iloc[0] if len(data) > 0 else None
        name = str(name_val) if pd.notna(name_val) else "Unknown"
        total = len(data)
        denied = int(data["is_denied"].sum())
        rejected = int(data["is_rejected"].sum())
        denied_or_rejected = int((data["is_denied"] | data["is_rejected"]).sum())
        high_risk = int((data["risk_level"] == "high").sum())
        medium_risk = int((data["risk_level"] == "medium").sum())
        low_risk = int((data["risk_level"] == "low").sum())
        avg_prob = float(data["denial_probability"].mean())
        total_billed = float(data["total_billed_amount"].sum())
        denied_billed = float(data[data["is_denied"]]["total_billed_amount"].sum())

        results.append({
            "id": str(group_id),
            "name": name,
            "total_claims": total,
            "denied_claims": denied,
            "rejected_claims": rejected,
            "denied_or_rejected": denied_or_rejected,
            "denial_rate": denied / total if total > 0 else 0.0,
            "rejection_rate": rejected / total if total > 0 else 0.0,
            "denial_or_rejection_rate": denied_or_rejected / total if total > 0 else 0.0,
            "avg_denial_probability": avg_prob,
            "high_risk_count": high_risk,
            "medium_risk_count": medium_risk,
            "low_risk_count": low_risk,
            "high_risk_pct": high_risk / total if total > 0 else 0.0,
            "total_billed": total_billed,
            "denied_billed": denied_billed,
            "denied_billed_pct": denied_billed / total_billed if total_billed > 0 else 0.0,
        })

    results.sort(key=lambda x: x["denial_rate"], reverse=True)
    return results

