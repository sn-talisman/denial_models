# Healthcare Denial Management API — Complete Reference

This document provides a complete reference for every endpoint exposed by the Healthcare Denial Management API. For a high-level overview, see the [README](README.md).

---

## Table of Contents

1. [Server & Interactive Docs](#server--interactive-docs)
2. [Authentication & CORS](#authentication--cors)
3. [Common Query Parameters](#common-query-parameters)
4. [Response Codes & Error Format](#response-codes--error-format)
5. [Health & Info Endpoints](#health--info-endpoints)
6. [Prediction Endpoints](#prediction-endpoints)
7. [Aggregate Analytics Endpoints](#aggregate-analytics-endpoints)
8. [Practice-Specific Analytics Endpoints](#practice-specific-analytics-endpoints)
9. [System-Wide Analytics Endpoints](#system-wide-analytics-endpoints)
10. [Client Examples](#client-examples)

---

## Server & Interactive Docs

### Starting the Server

```bash
DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001
```

### Interactive Documentation

| URL | Format | Best For |
|---|---|---|
| `http://localhost:8001/docs` | Swagger UI | Interactive testing — click "Try it out" on any endpoint |
| `http://localhost:8001/redoc` | ReDoc | Reading / printing / sharing |
| `http://localhost:8001/openapi.json` | OpenAPI 3.0 JSON | Import into Postman, Insomnia, or code generators |

---

## Authentication & CORS

**Authentication**: The API currently does not require authentication. For production deployment, add API-key or OAuth2/JWT middleware.

**CORS**: All origins are allowed (`allow_origins=["*"]`). Restrict this in production.

---

## Common Query Parameters

Several analytics endpoints share these query parameters:

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `days_back` | int | 365 | 1 – 3650 | Number of days of claim history to analyze |
| `min_claims` | int | 5 | 1+ | Minimum claims in a group to include it in results |
| `limit` | int | 20 | 1 – 100 | Maximum items to return (used by high-risk-claims) |

---

## Response Codes & Error Format

| Code | Meaning |
|---|---|
| `200 OK` | Successful request |
| `400 Bad Request` | Invalid parameters (e.g., batch too large) |
| `404 Not Found` | No claims found for the given practice GUID |
| `500 Internal Server Error` | Unexpected server error |
| `503 Service Unavailable` | Model not loaded (needs training) |

All error responses return:

```json
{
  "detail": "Human-readable error message"
}
```

---

## Health & Info Endpoints

### GET `/`

Root endpoint returning API information and a directory of all available endpoints.

**Response** `200`:

```json
{
  "name": "Healthcare Denial Management API",
  "version": "0.2.0",
  "documentation": {
    "swagger_ui": "/docs",
    "redoc": "/redoc",
    "openapi_json": "/openapi.json"
  },
  "endpoints": {
    "health": "/health",
    "readiness": "/ready",
    "predictions": {
      "predict": "/api/v1/predict",
      "predict_batch": "/api/v1/predict/batch",
      "model_info": "/api/v1/model/info"
    },
    "analytics": {
      "practices": "/api/v1/analytics/practices",
      "payers": "/api/v1/analytics/payers",
      "practice_payer_combos": "/api/v1/analytics/practice-payer",
      "overall_insights": "/api/v1/analytics/overall-insights",
      "practice_performance_summary": "/api/v1/analytics/practice/{practice_guid}/performance-summary",
      "practice_action_items": "/api/v1/analytics/practice/{practice_guid}/action-items",
      "practice_payer_performance": "/api/v1/analytics/practice/{practice_guid}/payer-performance",
      "practice_cpt_performance": "/api/v1/analytics/practice/{practice_guid}/cpt-performance",
      "practice_high_risk_claims": "/api/v1/analytics/practice/{practice_guid}/high-risk-claims",
      "practice_denial_reasons": "/api/v1/analytics/practice/{practice_guid}/denial-reasons",
      "practice_cpt_carc_correlation": "/api/v1/analytics/practice/{practice_guid}/cpt-carc-correlation",
      "practice_rejection_patterns": "/api/v1/analytics/practice/{practice_guid}/rejection-patterns"
    }
  }
}
```

---

### GET `/health`

Simple liveness check.

**Response** `200`:

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### GET `/ready`

Readiness check indicating the service can accept requests.

**Response** `200`:

```json
{
  "status": "ready"
}
```

---

## Prediction Endpoints

All prediction endpoints are under `/api/v1` with tag `predictions`.

---

### POST `/api/v1/predict`

Predict denial probability for a single claim with pre-engineered features.

**Request Body** — `PredictionRequest`:

| Field | Type | Required | Description |
|---|---|---|---|
| `claim_id` | string | Yes | Unique claim identifier |
| `features` | object | Yes | Dictionary of pre-engineered feature values (e.g., `{"total_billed_amount": 500.0, "payment_ratio": 0.3, ...}`) |
| `include_explanations` | bool | No (default: false) | If true, includes SHAP or model feature importance in the response |

**Example Request**:

```json
{
  "claim_id": "CLM-12345",
  "features": {
    "total_billed_amount": 1500.00,
    "total_paid_amount": 200.00,
    "payment_ratio": 0.133,
    "line_item_count": 3,
    "hist_denial_rate_cpt_payer": 0.45,
    "hist_denial_rate_practice": 0.65,
    "service_day_of_week": 2,
    "submission_lag_days": 14
  },
  "include_explanations": true
}
```

**Response** `200` — `PredictionResponse`:

| Field | Type | Description |
|---|---|---|
| `claim_id` | string | Echo of the input claim ID |
| `denial_probability` | float (0.0–1.0) | Calibrated probability of denial |
| `denial_prediction` | bool | Binary prediction (true = denied) |
| `risk_level` | string | `"low"` (< 0.3), `"medium"` (0.3–0.7), `"high"` (> 0.7) |
| `feature_importance` | object or null | Feature → importance mapping (if explanations requested) |
| `explanation_type` | string or null | `"SHAP"` or `"model_feature_importance"` |

**Example Response**:

```json
{
  "claim_id": "CLM-12345",
  "denial_probability": 0.82,
  "denial_prediction": true,
  "risk_level": "high",
  "feature_importance": {
    "hist_denial_rate_cpt_payer": 0.234,
    "payment_ratio": 0.189,
    "total_billed_amount": 0.145
  },
  "explanation_type": "SHAP"
}
```

**Notes**:
- Features not present in the trained model's feature list are ignored.
- Missing expected features are zero-filled with a warning log.
- The model has ~1,788 features; you only need to supply the ones you have.

---

### POST `/api/v1/predict/batch`

Predict denial probability for multiple claims in one request.

**Request Body** — `BatchPredictionRequest`:

| Field | Type | Required | Description |
|---|---|---|---|
| `claims` | array of `PredictionRequest` | Yes | List of individual prediction requests |
| `max_claims` | int | No (default: 1000) | Maximum batch size (server-side cap: 1000) |

**Example Request**:

```json
{
  "claims": [
    {
      "claim_id": "CLM-001",
      "features": {"total_billed_amount": 500.0, "line_item_count": 1}
    },
    {
      "claim_id": "CLM-002",
      "features": {"total_billed_amount": 2500.0, "line_item_count": 5}
    }
  ]
}
```

**Response** `200` — `BatchPredictionResponse`:

| Field | Type | Description |
|---|---|---|
| `predictions` | array of `PredictionResponse` | Prediction for each successfully processed claim |
| `total_processed` | int | Count of successfully processed claims |
| `errors` | array or null | List of `{"claim_id": "...", "error": "..."}` for failed claims |

**Error** `400`: Returned if `claims` array exceeds `max_claims`.

---

### GET `/api/v1/model/info`

Retrieve metadata about the currently loaded model.

**Response** `200` — `ModelInfoResponse`:

| Field | Type | Description |
|---|---|---|
| `model_type` | string | `"lightgbm"` or `"xgboost"` |
| `feature_count` | int | Number of features the model expects |
| `feature_columns` | array of string | Ordered list of all feature names |
| `training_date` | string or null | ISO date when the model was trained |
| `train_size` | int or null | Number of training samples |
| `validation_size` | int or null | Number of validation samples |
| `metrics` | object or null | Training and validation metrics |

**Example Response**:

```json
{
  "model_type": "lightgbm",
  "feature_count": 1788,
  "feature_columns": ["total_billed_amount", "payment_ratio", "..."],
  "train_size": 8520,
  "validation_size": 1217,
  "metrics": {
    "train": {
      "precision": 1.0,
      "recall": 0.9956,
      "f1_score": 0.9978,
      "roc_auc": 1.0
    },
    "validation": {
      "precision": 1.0,
      "recall": 0.9920,
      "f1_score": 0.9960,
      "roc_auc": 0.9985
    }
  }
}
```

---

## Aggregate Analytics Endpoints

All aggregate analytics endpoints are under `/api/v1/analytics` with tag `analytics`. They run the full prediction pipeline across all claims, then group results.

---

### GET `/api/v1/analytics/practices`

Analyze denial and rejection rates by practice.

**Query Parameters**: `days_back` (default 365), `min_claims` (default 5)

**Response** `200` — array of `PracticeAnalysisResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice display name |
| `total_claims` | int | Total claims in the period |
| `denied_claims` | int | Claims classified as denied |
| `rejected_claims` | int | Claims classified as rejected |
| `denied_or_rejected` | int | Union of denied and rejected |
| `denial_rate` | float | `denied_claims / total_claims` |
| `rejection_rate` | float | `rejected_claims / total_claims` |
| `denial_or_rejection_rate` | float | `denied_or_rejected / total_claims` |
| `avg_denial_probability` | float | Mean predicted denial probability |
| `high_risk_count` | int | Claims with risk_level = "high" |
| `medium_risk_count` | int | Claims with risk_level = "medium" |
| `low_risk_count` | int | Claims with risk_level = "low" |
| `high_risk_pct` | float | `high_risk_count / total_claims` |
| `total_billed` | float | Sum of billed amounts |
| `denied_billed` | float | Sum of billed amounts for denied claims |
| `denied_billed_pct` | float | `denied_billed / total_billed` |

Results are sorted by `denial_rate` descending.

---

### GET `/api/v1/analytics/payers`

Analyze denial and rejection rates by payer. Same schema as practices but keyed by `payer_id` / `payer_name`.

**Query Parameters**: `days_back` (default 365), `min_claims` (default 5)

**Response** `200` — array of `PayerAnalysisResponse` (same fields as `PracticeAnalysisResponse` but with `payer_id` / `payer_name`).

---

### GET `/api/v1/analytics/practice-payer`

Analyze denial rates for every practice-payer combination.

**Query Parameters**: `days_back` (default 365), `min_claims` (default 5)

**Response** `200` — array of `PracticePayerComboResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `payer_id` | string | Payer policy key |
| `payer_name` | string | Payer company name |
| `total_claims` | int | Claims for this combo |
| `denied_claims` | int | Denied claims |
| `rejected_claims` | int | Rejected claims |
| `denied_or_rejected` | int | Union |
| `denial_rate` | float | Denial rate |
| `rejection_rate` | float | Rejection rate |
| `denial_or_rejection_rate` | float | Combined rate |
| `avg_denial_probability` | float | Mean predicted probability |
| `high_risk_count` | int | High-risk claims |
| `high_risk_pct` | float | High-risk percentage |
| `total_billed` | float | Total billed |
| `denied_billed` | float | Denied billed amount |
| `denied_billed_pct` | float | Percentage of billed that was denied |

---

## Practice-Specific Analytics Endpoints

All endpoints below are under `/api/v1/analytics/practice/{practice_guid}`. The `practice_guid` is a UUID string identifying the practice in `cmn_practice`.

---

### GET `/api/v1/analytics/practice/{practice_guid}/performance-summary`

Comprehensive performance summary for a single practice.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `PerformanceSummaryResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `total_claims` | int | Total claims |
| `denied_claims` | int | Denied claims |
| `denial_rate` | float | Denial rate |
| `denial_rate_vs_overall` | float | Difference from system-wide denial rate (positive = worse) |
| `total_billed` | float | Total billed amount |
| `total_paid` | float | Total paid amount |
| `denied_amount` | float | Total billed amount of denied claims |
| `recovery_potential` | float | Estimated recoverable amount (30% of denied_amount) |
| `avg_denial_probability` | float | Mean predicted probability |
| `avg_probability_vs_overall` | float | Difference from system-wide average probability |
| `high_risk_claims` | int | Number of high-risk claims |
| `high_risk_pct` | float | Percentage of claims that are high-risk |
| `insights` | object | `PerformanceInsights` sub-object (see below) |

**`PerformanceInsights` sub-object**:

| Field | Type | Description |
|---|---|---|
| `trends` | object | Daily denial rate time series `{"YYYY-MM-DD": rate, ...}` |
| `comparisons` | object | Reserved for benchmark comparisons |
| `key_issues` | array of string | e.g., `"Very high denial rate (71.6%) - above 50%"` |
| `risk_factors` | array of string | e.g., `"High denial rate with Medicare of Maryland"` |

**Error** `404`: No claims found for the given practice GUID.

---

### GET `/api/v1/analytics/practice/{practice_guid}/action-items`

Prioritized, actionable recommendations sorted by financial impact.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `PrioritizedActionItemsResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `action_items` | array of `ActionItemResponse` | Up to 15 items, sorted by `financial_impact` desc |

**`ActionItemResponse`**:

| Field | Type | Description |
|---|---|---|
| `priority` | string | `"HIGH"` or `"MEDIUM"` |
| `title` | string | Human-readable title, e.g., `"High Denial Rate with Medicare"` |
| `financial_impact` | float | Dollar amount at risk |
| `recommendation` | string | Actionable recommendation text |
| `details` | string | Supporting data, e.g., `"94.3% denial rate on 488 claims ($1,127,000 at risk)"` |
| `type` | string | Source: `"payer"`, `"cpt"`, `"carc"`, or `"cpt_carc"` |
| `payer_name` | string or null | Payer name (if type = payer) |
| `cpt_code` | string or null | CPT code (if type = cpt or cpt_carc) |
| `carc_code` | int or null | CARC code (if type = carc or cpt_carc) |

**Action item generation logic**:
1. **Payer patterns**: Payers with > 50% denial rate and >= 3 claims.
2. **CPT patterns**: CPT codes with > 40% denial rate and >= 5 claims. Includes top payer contributing to denials.
3. **CARC insights**: Top CARC code by adjustment amount (if > $1,000).
4. **CPT-CARC correlation**: Top CPT-CARC combination by adjustment amount (if > $5,000).

---

### GET `/api/v1/analytics/practice/{practice_guid}/payer-performance`

Denial performance broken down by insurance payer.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `PayerPerformanceResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `payers` | array of `PayerPerformanceItem` | Sorted by `denied_amount` descending |

**`PayerPerformanceItem`**:

| Field | Type | Description |
|---|---|---|
| `payer_name` | string | Insurance company name |
| `total_claims` | int | Total claims with this payer |
| `denied_claims` | int | Denied claims |
| `denial_rate` | float | `denied / total` |
| `total_billed` | float | Sum of billed amounts |
| `total_paid` | float | Sum of paid amounts |
| `denied_amount` | float | Sum of billed for denied claims |
| `avg_denial_probability` | float | Mean predicted probability |

---

### GET `/api/v1/analytics/practice/{practice_guid}/cpt-performance`

Denial performance broken down by CPT/HCPCS procedure code.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `CPTPerformanceResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `cpt_codes` | array of `CPTPerformanceItem` | Sorted by `denied_amount` descending |

**`CPTPerformanceItem`**:

| Field | Type | Description |
|---|---|---|
| `cpt_code` | string | CPT/HCPCS code (e.g., `"97110"`, `"G0283"`) |
| `total_claims` | int | Total claims with this code |
| `denied_claims` | int | Denied claims |
| `denial_rate` | float | `denied / total` |
| `total_billed` | float | Sum of billed amounts |
| `denied_amount` | float | Sum of billed for denied claims |
| `avg_denial_probability` | float | Mean predicted probability |

---

### GET `/api/v1/analytics/practice/{practice_guid}/high-risk-claims`

Individual claims with the highest predicted denial probability.

**Query Parameters**: `days_back` (default 365), `limit` (default 20, max 100)

**Response** `200` — `HighRiskClaimsResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `high_risk_claims` | array of `HighRiskClaimItem` | Sorted by `denial_probability` descending |

**`HighRiskClaimItem`**:

| Field | Type | Description |
|---|---|---|
| `claim_id` | string or null | Claim reference ID |
| `payer_name` | string | Payer name |
| `cpt_code` | string or null | Primary CPT code |
| `denial_probability` | float | Predicted denial probability |
| `billed_amount` | float | Total billed amount |
| `is_denied` | bool | Whether the claim was actually denied |

---

### GET `/api/v1/analytics/practice/{practice_guid}/denial-reasons`

CARC and RARC code frequency and financial impact analysis.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `CARCRARCAnalysisResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `carc_codes` | array of `CARCCodeItem` | Sorted by `total_adjustment_amount` descending |
| `rarc_codes` | array of `RARCCodeItem` | Sorted by `total_adjustment_amount` descending |

**`CARCCodeItem`**:

| Field | Type | Description |
|---|---|---|
| `carc_code` | int | Claim Adjustment Reason Code number |
| `occurrence_count` | int | Total times this code appeared |
| `affected_claims` | int | Distinct claims with this code |
| `total_adjustment_amount` | float | Sum of adjustment amounts |
| `description` | string | Human-readable description (e.g., "Charge exceeds fee schedule...") |

**`RARCCodeItem`**:

| Field | Type | Description |
|---|---|---|
| `rarc_code` | string | Remittance Advice Remark Code |
| `occurrence_count` | int | Total occurrences |
| `affected_claims` | int | Distinct claims |
| `total_adjustment_amount` | float | Sum of adjustments |

**Common CARC codes** and their meanings:

| CARC | Description |
|---|---|
| 1 | Deductible Amount |
| 2 | Coinsurance Amount |
| 3 | Co-payment Amount |
| 4 | Procedure code inconsistent with modifier |
| 16 | Claim lacks information for adjudication |
| 18 | Exact duplicate claim |
| 29 | Time limit for filing expired |
| 45 | Charge exceeds fee schedule / maximum allowable |
| 50 | Not deemed medical necessity |
| 95 | Processed per plan provisions |

---

### GET `/api/v1/analytics/practice/{practice_guid}/cpt-carc-correlation`

Which CPT codes are being denied for which reasons.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `CPTCARCCorrelationResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `cpt_carc` | array of `CPTCARCCorrelationItem` | Sorted by `total_adjustment_amount` descending |
| `cpt_rarc` | array of `CPTRARCCorrelationItem` | Sorted by `total_adjustment_amount` descending |

**`CPTCARCCorrelationItem`**:

| Field | Type | Description |
|---|---|---|
| `cpt_code` | string | CPT/HCPCS code |
| `carc_code` | int | CARC code |
| `occurrence_count` | int | Times this CPT-CARC combination appeared |
| `affected_claims` | int | Distinct claims |
| `total_adjustment_amount` | float | Sum of adjustments |
| `carc_description` | string | Human-readable CARC description |

**`CPTRARCCorrelationItem`**: Same as above but with `rarc_code` (string) instead of `carc_code`.

---

### GET `/api/v1/analytics/practice/{practice_guid}/rejection-patterns`

Missing or invalid field patterns that cause claim rejections, analyzed per CPT code.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `RejectionPatternResponse`:

| Field | Type | Description |
|---|---|---|
| `practice_id` | string | Practice GUID |
| `practice_name` | string | Practice name |
| `rejection_patterns` | array of `RejectionPatternItem` | Sorted by `rejection_risk_score` descending |

**`RejectionPatternItem`**:

| Field | Type | Description |
|---|---|---|
| `cpt_code` | string | CPT/HCPCS code |
| `total_rejections` | int | Rejected claims with this CPT |
| `total_claims` | int | Total claims with this CPT |
| `rejection_rate` | float | `total_rejections / total_claims` |
| `missing_patient_id` | int | Count of claims missing patient ID |
| `missing_provider_id` | int | Count of claims missing provider ID |
| `missing_service_date` | int | Count of claims missing service date |
| `missing_submitted_date` | int | Count of claims missing submitted date |
| `invalid_date_order` | int | Claims where submitted_date < service_date |
| `missing_cpt_in_line_items` | int | Line items with empty CPT code |
| `invalid_cpt_count` | int | Line items with invalid CPT/HCPCS format |
| `missing_billed_amount` | int | Claims with zero or null billed amount |
| `missing_line_items` | int | Claims with no line items |
| `rejection_risk_score` | int | Weighted composite score (see below) |

**Rejection Risk Score Calculation**:

```
risk_score = (missing_patient_id × 3)
           + (missing_provider_id × 3)
           + (missing_service_date × 3)
           + (missing_submitted_date × 4)
           + (invalid_date_order × 3)
           + (missing_cpt_in_line_items × 2)
           + (invalid_cpt_count × 2)
           + (missing_billed_amount × 2)
           + (missing_line_items × 5)
```

Higher weights reflect fields that are more likely to cause rejection.

---

## System-Wide Analytics Endpoints

### GET `/api/v1/analytics/overall-insights`

Aggregated insights across all practices. Iterates over every practice, fetches data, and aggregates.

**Query Parameters**: `days_back` (default 365)

**Response** `200` — `OverallInsightsResponse`:

| Field | Type | Description |
|---|---|---|
| `total_practices` | int | Number of active practices with claims |
| `total_claims` | int | Total claims across all practices |
| `total_denials` | int | Total denied claims |
| `overall_denial_rate` | float | System-wide denial rate |
| `total_denied_amount` | float | Sum of billed amounts for denied claims |
| `top_carc_codes` | array of object | Top 10 CARC codes by total adjustment amount |
| `top_payers` | array of object | Top 10 payers by denied amount |
| `top_cpt_codes` | array of object | Top 10 CPT codes by denied amount |
| `key_findings` | array of string | Auto-generated narrative findings |

**`top_carc_codes` item**:

```json
{
  "carc_code": 45,
  "occurrence_count": 4551,
  "total_amount": 1456154.07
}
```

**`top_payers` item**:

```json
{
  "payer_name": "Medicare of Maryland - J12",
  "total_claims": 488,
  "denied_claims": 460,
  "denial_rate": 0.9426,
  "denied_amount": 1127000.00
}
```

**`top_cpt_codes` item**:

```json
{
  "cpt_code": "97110",
  "total_claims": 1200,
  "denied_claims": 900,
  "denial_rate": 0.75,
  "denied_amount": 450000.00
}
```

**`key_findings` examples**:

```json
[
  "Overall denial rate is very high (71.6%)",
  "Top denial reason: Charge exceeds fee schedule (CARC 45) ($1,456,154.07)",
  "Top payer by denial amount: Medicare of Maryland - J12 ($1,127,000.00)",
  "Potential recovery through appeals: $686,732.61 (30% recovery rate)"
]
```

**Note**: This endpoint can be slow (~30–60 seconds) as it processes every practice sequentially. Consider caching the result for production use.

---

## Client Examples

### curl

```bash
# Health check
curl http://localhost:8001/health

# List all practices
curl "http://localhost:8001/api/v1/analytics/practices?days_back=365&min_claims=1"

# Performance summary for a practice
curl "http://localhost:8001/api/v1/analytics/practice/ee5ed349-d9dd-4bf5-81a5-aa503a261961/performance-summary?days_back=365"

# Action items
curl "http://localhost:8001/api/v1/analytics/practice/ee5ed349-d9dd-4bf5-81a5-aa503a261961/action-items"

# Denial reasons
curl "http://localhost:8001/api/v1/analytics/practice/ee5ed349-d9dd-4bf5-81a5-aa503a261961/denial-reasons"

# CPT-CARC correlation
curl "http://localhost:8001/api/v1/analytics/practice/ee5ed349-d9dd-4bf5-81a5-aa503a261961/cpt-carc-correlation"

# Rejection patterns
curl "http://localhost:8001/api/v1/analytics/practice/ee5ed349-d9dd-4bf5-81a5-aa503a261961/rejection-patterns"

# Single prediction
curl -X POST http://localhost:8001/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "claim_id": "TEST-001",
    "features": {
      "total_billed_amount": 1500.0,
      "payment_ratio": 0.13,
      "line_item_count": 3,
      "hist_denial_rate_cpt_payer": 0.45
    }
  }'

# Model info
curl http://localhost:8001/api/v1/model/info

# Overall insights
curl "http://localhost:8001/api/v1/analytics/overall-insights?days_back=365"
```

### Python

```python
import requests

BASE_URL = "http://localhost:8001"

# Get all practices
practices = requests.get(f"{BASE_URL}/api/v1/analytics/practices", params={"min_claims": 1}).json()
for p in practices[:5]:
    print(f"{p['practice_name']}: {p['denial_rate']:.1%} denial rate ({p['total_claims']} claims)")

# Get performance summary
guid = practices[0]["practice_id"]
summary = requests.get(f"{BASE_URL}/api/v1/analytics/practice/{guid}/performance-summary").json()
print(f"\nDenial Rate: {summary['denial_rate']:.1%}")
print(f"Denied Amount: ${summary['denied_amount']:,.2f}")
print(f"Recovery Potential: ${summary['recovery_potential']:,.2f}")
print(f"Key Issues: {summary['insights']['key_issues']}")

# Get action items
actions = requests.get(f"{BASE_URL}/api/v1/analytics/practice/{guid}/action-items").json()
for item in actions["action_items"][:3]:
    print(f"\n[{item['priority']}] {item['title']}")
    print(f"  Impact: ${item['financial_impact']:,.2f}")
    print(f"  {item['recommendation']}")

# Make a prediction
result = requests.post(f"{BASE_URL}/api/v1/predict", json={
    "claim_id": "TEST-001",
    "features": {"total_billed_amount": 1500.0, "payment_ratio": 0.13},
    "include_explanations": True,
}).json()
print(f"\nPrediction: {result['denial_probability']:.1%} ({result['risk_level']})")
```

### JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8001';

// Get practices
const practices = await fetch(`${BASE_URL}/api/v1/analytics/practices?min_claims=1`).then(r => r.json());

// Get performance summary
const guid = practices[0].practice_id;
const summary = await fetch(`${BASE_URL}/api/v1/analytics/practice/${guid}/performance-summary`).then(r => r.json());

console.log(`Denial Rate: ${(summary.denial_rate * 100).toFixed(1)}%`);
console.log(`Recovery Potential: $${summary.recovery_potential.toLocaleString()}`);
```

---

## Schema Source

All Pydantic schemas are defined in `src/api/schemas.py`. The OpenAPI schema is auto-generated by FastAPI and available at `/openapi.json`.
