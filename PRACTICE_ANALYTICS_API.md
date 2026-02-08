# Practice Analytics API Endpoints

This document describes the new practice-specific analytics API endpoints that provide actionable insights for individual practices.

## Overview

All endpoints follow the pattern:
```
GET /api/v1/analytics/practice/{practice_guid}/{analysis_type}?days_back={days}
```

Where:
- `practice_guid`: The unique identifier (GUID) for the practice
- `analysis_type`: One of the analysis types described below
- `days_back`: Number of days to look back (default: 365, max: 3650)

## Endpoints

### 1. Performance Summary

**Endpoint**: `GET /api/v1/analytics/practice/{practice_guid}/performance-summary`

**Description**: Returns overall performance metrics for a practice, including denial rates, financial metrics, and risk indicators.

**Query Parameters**:
- `days_back` (int, default: 365): Number of days to analyze

**Response Schema**:
```json
{
  "practice_id": "string",
  "practice_name": "string",
  "total_claims": 0,
  "denied_claims": 0,
  "denial_rate": 0.0,
  "denial_rate_vs_overall": 0.0,
  "total_billed": 0.0,
  "total_paid": 0.0,
  "denied_amount": 0.0,
  "avg_denial_probability": 0.0,
  "avg_probability_vs_overall": 0.0,
  "high_risk_claims": 0,
  "high_risk_pct": 0.0
}
```

**Example Request**:
```bash
curl "http://localhost:8000/api/v1/analytics/practice/abc123/performance-summary?days_back=365"
```

---

### 2. Prioritized Action Items

**Endpoint**: `GET /api/v1/analytics/practice/{practice_guid}/action-items`

**Description**: Returns prioritized action items ranked by financial impact, with specific recommendations for improving denial rates.

**Query Parameters**:
- `days_back` (int, default: 365): Number of days to analyze

**Response Schema**:
```json
{
  "practice_id": "string",
  "practice_name": "string",
  "action_items": [
    {
      "priority": "HIGH|MEDIUM|LOW",
      "title": "string",
      "financial_impact": 0.0,
      "recommendation": "string",
      "details": "string",
      "type": "payer|cpt",
      "payer_name": "string (optional)",
      "cpt_code": "string (optional)"
    }
  ]
}
```

**Example Request**:
```bash
curl "http://localhost:8000/api/v1/analytics/practice/abc123/action-items?days_back=365"
```

---

### 3. Performance by Payer

**Endpoint**: `GET /api/v1/analytics/practice/{practice_guid}/payer-performance`

**Description**: Returns aggregated performance metrics broken down by payer, showing denial rates and financial impact per payer.

**Query Parameters**:
- `days_back` (int, default: 365): Number of days to analyze

**Response Schema**:
```json
{
  "practice_id": "string",
  "practice_name": "string",
  "payers": [
    {
      "payer_name": "string",
      "total_claims": 0,
      "denied_claims": 0,
      "denial_rate": 0.0,
      "total_billed": 0.0,
      "total_paid": 0.0,
      "denied_amount": 0.0,
      "avg_denial_probability": 0.0
    }
  ]
}
```

**Example Request**:
```bash
curl "http://localhost:8000/api/v1/analytics/practice/abc123/payer-performance?days_back=365"
```

---

### 4. Performance by CPT Code

**Endpoint**: `GET /api/v1/analytics/practice/{practice_guid}/cpt-performance`

**Description**: Returns aggregated performance metrics broken down by CPT code, showing which codes have the highest denial rates and financial impact.

**Query Parameters**:
- `days_back` (int, default: 365): Number of days to analyze

**Response Schema**:
```json
{
  "practice_id": "string",
  "practice_name": "string",
  "cpt_codes": [
    {
      "cpt_code": "string",
      "total_claims": 0,
      "denied_claims": 0,
      "denial_rate": 0.0,
      "total_billed": 0.0,
      "denied_amount": 0.0,
      "avg_denial_probability": 0.0
    }
  ]
}
```

**Example Request**:
```bash
curl "http://localhost:8000/api/v1/analytics/practice/abc123/cpt-performance?days_back=365"
```

---

### 5. High Risk Claims

**Endpoint**: `GET /api/v1/analytics/practice/{practice_guid}/high-risk-claims`

**Description**: Returns a list of high-risk claims that require immediate attention, sorted by denial probability.

**Query Parameters**:
- `days_back` (int, default: 365): Number of days to analyze
- `limit` (int, default: 20, max: 100): Maximum number of claims to return

**Response Schema**:
```json
{
  "practice_id": "string",
  "practice_name": "string",
  "high_risk_claims": [
    {
      "claim_id": "string (optional)",
      "payer_name": "string",
      "cpt_code": "string (optional)",
      "denial_probability": 0.0,
      "billed_amount": 0.0,
      "is_denied": false
    }
  ]
}
```

**Example Request**:
```bash
curl "http://localhost:8000/api/v1/analytics/practice/abc123/high-risk-claims?days_back=365&limit=20"
```

---

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `404 Not Found`: Practice not found or no claims found for the specified period
- `500 Internal Server Error`: Server error during analysis

Error response format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Implementation Details

### Data Processing

1. **Feature Engineering**: All endpoints use the optimized batch feature engineering pipeline
2. **Predictions**: ML model predictions are generated for all claims in the analysis period
3. **Aggregation**: Results are aggregated by practice, payer, or CPT code as appropriate
4. **Caching**: Consider implementing caching for frequently accessed practice data

### Performance Considerations

- Feature engineering and predictions are performed on-demand for each request
- For large practices with many claims, requests may take 10-30 seconds
- Consider implementing:
  - Background job processing for large analyses
  - Caching of results for frequently accessed practices
  - Pagination for high-risk claims endpoint

### Getting Practice GUIDs

To find practice GUIDs, you can use the existing `/api/v1/analytics/practices` endpoint which returns a list of all practices with their IDs.

## Testing

A test script is available at `scripts/test_practice_analytics_api.py`. Update the `practice_guid` variable with an actual practice GUID from your database before running.

```bash
python scripts/test_practice_analytics_api.py
```

## Example Usage

### Complete Workflow

1. **Get practice list**:
   ```bash
   curl "http://localhost:8000/api/v1/analytics/practices?days_back=365"
   ```

2. **Get performance summary for a practice**:
   ```bash
   curl "http://localhost:8000/api/v1/analytics/practice/{practice_guid}/performance-summary?days_back=365"
   ```

3. **Get prioritized action items**:
   ```bash
   curl "http://localhost:8000/api/v1/analytics/practice/{practice_guid}/action-items?days_back=365"
   ```

4. **Investigate specific payer issues**:
   ```bash
   curl "http://localhost:8000/api/v1/analytics/practice/{practice_guid}/payer-performance?days_back=365"
   ```

5. **Review high-risk claims**:
   ```bash
   curl "http://localhost:8000/api/v1/analytics/practice/{practice_guid}/high-risk-claims?days_back=365&limit=50"
   ```

