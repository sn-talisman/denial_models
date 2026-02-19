"""Tests for the practice insights report generator.

These tests import the key functions from ``scripts/generate_practice_insights_via_api.py``
and verify that:

1. ``call_api_endpoint`` handles success and failure correctly.
2. ``generate_markdown_for_practice`` assembles markdown from API responses.
3. ``get_practices_with_claims`` processes the API response.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Optional, Dict, Any

import pytest

# The script lives outside the package; add its parent to sys.path so we can import.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

# Import functions under test
from generate_practice_insights_via_api import (
    call_api_endpoint,
    generate_markdown_for_practice,
    get_practices_with_claims,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _api_perf_summary() -> dict:
    return {
        "practice_id": "p-1",
        "practice_name": "Test Practice",
        "total_claims": 500,
        "denied_claims": 100,
        "denial_rate": 0.20,
        "denial_rate_vs_overall": -0.04,
        "total_billed": 250000.0,
        "total_paid": 200000.0,
        "denied_amount": 50000.0,
        "recovery_potential": 15000.0,
        "avg_denial_probability": 0.18,
        "avg_probability_vs_overall": 0.08,
        "high_risk_claims": 30,
        "high_risk_pct": 0.06,
        "insights": {"trends": {}, "key_issues": [], "risk_factors": []},
    }


def _api_action_items() -> dict:
    return {
        "practice_id": "p-1",
        "practice_name": "Test Practice",
        "action_items": [
            {
                "priority": "HIGH",
                "title": "Review payer Aetna",
                "financial_impact": 25000.0,
                "recommendation": "Review contract",
                "details": "50% denial rate with Aetna",
                "type": "payer",
                "payer_name": "Aetna",
            },
        ],
    }


def _api_payer_perf() -> dict:
    return {
        "practice_id": "p-1",
        "practice_name": "Test Practice",
        "payers": [
            {
                "payer_name": "Aetna",
                "total_claims": 200,
                "denied_claims": 60,
                "denial_rate": 0.30,
                "total_billed": 100000.0,
                "total_paid": 70000.0,
                "denied_amount": 30000.0,
                "avg_denial_probability": 0.28,
            },
        ],
    }


# ── call_api_endpoint ───────────────────────────────────────────────────────


class TestCallApiEndpoint:

    @patch("generate_practice_insights_via_api.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"total_claims": 100}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = call_api_endpoint("/api/v1/analytics/practice/p-1/performance-summary", "Test")
        assert result == {"total_claims": 100}

    @patch("generate_practice_insights_via_api.requests.get")
    def test_timeout(self, mock_get):
        import requests as real_requests
        mock_get.side_effect = real_requests.exceptions.Timeout("timed out")
        result = call_api_endpoint("/api/v1/some-endpoint", "Timeout Test")
        assert result is None

    @patch("generate_practice_insights_via_api.requests.get")
    def test_http_error(self, mock_get):
        import requests as real_requests
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = real_requests.exceptions.HTTPError(
            "500 Server Error", response=mock_resp,
        )
        mock_get.return_value = mock_resp
        result = call_api_endpoint("/api/v1/some-endpoint", "Error Test")
        assert result is None


# ── generate_markdown_for_practice ──────────────────────────────────────────


class TestGenerateMarkdown:

    @patch("generate_practice_insights_via_api.call_api_endpoint")
    def test_generates_markdown_with_data(self, mock_call):
        """Should produce non-empty markdown when all endpoints return data."""
        def side_effect(endpoint, desc):
            if "performance-summary" in endpoint:
                return _api_perf_summary()
            if "action-items" in endpoint:
                return _api_action_items()
            if "payer-performance" in endpoint:
                return _api_payer_perf()
            if "cpt-performance" in endpoint:
                return {"practice_id": "p-1", "practice_name": "Test", "cpt_codes": []}
            if "high-risk-claims" in endpoint:
                return {"practice_id": "p-1", "practice_name": "Test", "high_risk_claims": []}
            if "denial-reasons" in endpoint:
                return {"practice_id": "p-1", "practice_name": "Test", "carc_codes": [], "rarc_codes": []}
            if "cpt-carc-correlation" in endpoint:
                return {"practice_id": "p-1", "practice_name": "Test", "cpt_carc": [], "cpt_rarc": []}
            if "rejection-patterns" in endpoint:
                return {"practice_id": "p-1", "practice_name": "Test", "rejection_patterns": []}
            return None

        mock_call.side_effect = side_effect

        md, summary = generate_markdown_for_practice(
            practice_id="p-1",
            practice_name="Test Practice",
            days_back=90,
            practice_num=1,
            total_practices=1,
        )
        assert len(md) > 0
        assert "Test Practice" in md
        assert summary is not None

    @patch("generate_practice_insights_via_api.call_api_endpoint")
    def test_returns_empty_when_no_data(self, mock_call):
        """Should return empty string when performance summary is unavailable."""
        mock_call.return_value = None
        md, summary = generate_markdown_for_practice(
            practice_id="p-1",
            practice_name="Ghost Practice",
            days_back=90,
        )
        assert md == ""
        assert summary is None

    @patch("generate_practice_insights_via_api.call_api_endpoint")
    def test_reuses_cached_summary(self, mock_call):
        """When a pre-fetched performance_summary is passed, it should not call the summary endpoint again."""
        cached = _api_perf_summary()

        call_count = {"n": 0}
        def side_effect(endpoint, desc):
            call_count["n"] += 1
            if "performance-summary" in endpoint:
                pytest.fail("Should not call performance-summary when cached")
            return {"practice_id": "p-1", "practice_name": "Test", "action_items": [],
                    "payers": [], "cpt_codes": [], "high_risk_claims": [],
                    "carc_codes": [], "rarc_codes": [], "cpt_carc": [], "cpt_rarc": [],
                    "rejection_patterns": []}

        mock_call.side_effect = side_effect

        md, summary = generate_markdown_for_practice(
            practice_id="p-1",
            practice_name="Test Practice",
            days_back=90,
            performance_summary=cached,
        )
        assert summary is not None
        assert len(md) > 0


# ── get_practices_with_claims ───────────────────────────────────────────────


class TestGetPracticesWithClaims:

    @patch("generate_practice_insights_via_api.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"practice_id": "p-1", "practice_name": "Alpha", "total_claims": 100},
            {"practice_id": "p-2", "practice_name": "Beta", "total_claims": 50},
        ]
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        practices = get_practices_with_claims(days_back=30)
        assert len(practices) == 2
        assert practices[0]["practice_id"] == "p-1"
        assert practices[1]["practice_name"] == "Beta"

