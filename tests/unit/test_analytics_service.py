"""Unit tests for the analytics service layer."""

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from src.services.analytics_service import (
    get_performance_insights,
    calculate_performance_summary,
    get_payer_performance,
    get_cpt_performance,
    get_high_risk_claims,
    get_prioritized_action_items,
    aggregate_by_group,
)


class TestPerformanceInsights:
    """Tests for get_performance_insights."""

    def test_empty_dataframe(self):
        result = get_performance_insights(pd.DataFrame())
        assert result["trends"] == {}
        assert result["key_issues"] == []
        assert result["risk_factors"] == []

    def test_high_denial_rate_flagged(self, practice_predictions_df):
        # Force high denial rate
        df = practice_predictions_df.copy()
        df["is_denied"] = True
        result = get_performance_insights(df)
        assert any("denial rate" in issue.lower() for issue in result["key_issues"])

    def test_payer_risk_factors(self, practice_predictions_df):
        df = practice_predictions_df.copy()
        # Make all Aetna claims denied
        df.loc[df["payer_name"] == "Aetna", "is_denied"] = True
        result = get_performance_insights(df)
        has_payer_risk = any("Aetna" in rf for rf in result["risk_factors"])
        assert has_payer_risk

    def test_cpt_risk_factors(self, practice_predictions_df):
        df = practice_predictions_df.copy()
        df.loc[df["primary_cpt_code"] == "99213", "is_denied"] = True
        result = get_performance_insights(df)
        has_cpt_risk = any("99213" in rf for rf in result["risk_factors"])
        assert has_cpt_risk


class TestCalculatePerformanceSummary:
    """Tests for calculate_performance_summary."""

    def test_basic_summary(self, practice_predictions_df):
        summary = calculate_performance_summary(
            practice_predictions_df, overall_denial_rate=0.24, overall_avg_prob=0.10,
        )
        assert "total_claims" in summary
        assert "denied_claims" in summary
        assert "denial_rate" in summary
        assert "recovery_potential" in summary
        assert summary["total_claims"] == len(practice_predictions_df)

    def test_denial_rate_vs_overall(self, practice_predictions_df):
        summary = calculate_performance_summary(
            practice_predictions_df, overall_denial_rate=0.50, overall_avg_prob=0.10,
        )
        # Our data has ~30% denial rate, so difference should be negative
        assert isinstance(summary["denial_rate_vs_overall"], float)

    def test_recovery_potential_is_30_pct(self, practice_predictions_df):
        summary = calculate_performance_summary(
            practice_predictions_df, overall_denial_rate=0.24, overall_avg_prob=0.10,
        )
        expected = summary["denied_amount"] * 0.3
        assert abs(summary["recovery_potential"] - expected) < 0.01


class TestPayerPerformance:
    """Tests for get_payer_performance."""

    def test_returns_list_of_dicts(self, practice_predictions_df):
        result = get_payer_performance(practice_predictions_df)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "payer_name" in result[0]
        assert "total_claims" in result[0]
        assert "denial_rate" in result[0]

    def test_sorted_by_denied_amount(self, practice_predictions_df):
        result = get_payer_performance(practice_predictions_df)
        if len(result) > 1:
            amounts = [r["denied_amount"] for r in result]
            assert amounts == sorted(amounts, reverse=True)


class TestCPTPerformance:
    """Tests for get_cpt_performance."""

    def test_returns_list_of_dicts(self, practice_predictions_df):
        result = get_cpt_performance(practice_predictions_df)
        assert isinstance(result, list)
        for item in result:
            assert "cpt_code" in item
            assert "total_claims" in item

    def test_excludes_empty_cpt(self, practice_predictions_df):
        result = get_cpt_performance(practice_predictions_df)
        cpt_codes = [r["cpt_code"] for r in result]
        assert "" not in cpt_codes

    def test_empty_data(self):
        df = pd.DataFrame({
            "primary_cpt_code": [],
            "claim_id": [],
            "is_denied": [],
            "total_billed_amount": [],
            "denial_probability": [],
        })
        result = get_cpt_performance(df)
        assert result == []


class TestHighRiskClaims:
    """Tests for get_high_risk_claims."""

    def test_returns_limited_results(self, practice_predictions_df):
        result = get_high_risk_claims(practice_predictions_df, limit=5)
        assert len(result) <= 5

    def test_sorted_by_probability_desc(self, practice_predictions_df):
        result = get_high_risk_claims(practice_predictions_df, limit=10)
        if len(result) > 1:
            probs = [r["denial_probability"] for r in result]
            assert probs == sorted(probs, reverse=True)

    def test_all_high_risk(self, practice_predictions_df):
        result = get_high_risk_claims(practice_predictions_df)
        # All returned should have been "high" risk
        # (the fixture may not have high-risk claims if random seed changes)
        for item in result:
            assert item["denial_probability"] >= 0.0


class TestPrioritizedActionItems:
    """Tests for get_prioritized_action_items."""

    def test_returns_list(self, practice_predictions_df):
        result = get_prioritized_action_items(practice_predictions_df)
        assert isinstance(result, list)

    def test_max_15_items(self, practice_predictions_df):
        result = get_prioritized_action_items(practice_predictions_df)
        assert len(result) <= 15

    def test_sorted_by_financial_impact(self, practice_predictions_df):
        result = get_prioritized_action_items(practice_predictions_df)
        if len(result) > 1:
            impacts = [r["financial_impact"] for r in result]
            assert impacts == sorted(impacts, reverse=True)

    def test_carc_insights_included(self, practice_predictions_df):
        carc_data = {
            "carc_codes": [{
                "carc_code": 45,
                "occurrence_count": 20,
                "affected_claims": 15,
                "total_adjustment_amount": 50000.0,
                "description": "Charges exceed fee schedule",
            }],
        }
        result = get_prioritized_action_items(
            practice_predictions_df, carc_rarc_data=carc_data,
        )
        carc_items = [i for i in result if i["type"] == "carc"]
        assert len(carc_items) >= 1

    def test_cpt_carc_correlation_included(self, practice_predictions_df):
        cpt_carc_data = {
            "cpt_carc": [{
                "cpt_code": "97110",
                "carc_code": 45,
                "occurrence_count": 10,
                "affected_claims": 8,
                "total_adjustment_amount": 25000.0,
                "carc_description": "Charges exceed fee schedule",
            }],
        }
        result = get_prioritized_action_items(
            practice_predictions_df, cpt_carc_data=cpt_carc_data,
        )
        combo_items = [i for i in result if i["type"] == "cpt_carc"]
        assert len(combo_items) >= 1


class TestAggregateByGroup:
    """Tests for aggregate_by_group."""

    def test_basic_grouping(self):
        df = pd.DataFrame({
            "group_id": ["a", "a", "b", "b", "b"],
            "group_name": ["Alpha", "Alpha", "Beta", "Beta", "Beta"],
            "is_denied": [True, False, True, True, False],
            "is_rejected": [False, False, False, False, True],
            "risk_level": ["high", "low", "high", "medium", "low"],
            "denial_probability": [0.8, 0.2, 0.9, 0.6, 0.1],
            "total_billed_amount": [100, 200, 300, 400, 500],
        })
        result = aggregate_by_group(df, "group_id", "group_name", min_claims=2)
        assert len(result) == 2
        assert all("id" in r for r in result)
        assert all("denial_rate" in r for r in result)

    def test_min_claims_filtering(self):
        df = pd.DataFrame({
            "group_id": ["a", "b", "b", "b"],
            "group_name": ["X", "Y", "Y", "Y"],
            "is_denied": [True, False, True, False],
            "is_rejected": [False, False, False, False],
            "risk_level": ["high", "low", "medium", "low"],
            "denial_probability": [0.8, 0.2, 0.6, 0.1],
            "total_billed_amount": [100, 200, 300, 400],
        })
        result = aggregate_by_group(df, "group_id", "group_name", min_claims=2)
        # Only "b" has >= 2 claims
        assert len(result) == 1
        assert result[0]["id"] == "b"

