# Healthcare Denial Management API - Complete Documentation

## Interactive API Documentation

FastAPI automatically generates interactive API documentation that you can access when the server is running:

### Swagger UI (Interactive)
**URL**: `http://localhost:8001/docs`

- Interactive API explorer
- Try out endpoints directly in the browser
- See request/response schemas
- Test with real data

### ReDoc (Alternative Documentation)
**URL**: `http://localhost:8001/redoc`

- Clean, readable documentation format
- Better for printing/sharing
- All endpoints with detailed descriptions

### OpenAPI JSON Schema
**URL**: `http://localhost:8001/openapi.json`

- Machine-readable API schema
- Can be imported into API clients (Postman, Insomnia, etc.)
- Used for code generation

## API Base URL

```
http://localhost:8001
```

## Quick Start

1. **Start the API server**:
   ```bash
   DATABASE_URL="postgresql+asyncpg://tebra_user:tebra_password@localhost:5432/tebra_dw" \
   venv/bin/python3 -m uvicorn src.api.app:app --host 0.0.0.0 --port 8001
   ```

2. **Access the documentation**:
   - Open `http://localhost:8001/docs` in your browser
   - Or visit `http://localhost:8001/redoc` for ReDoc format

3. **Test the API**:
   - Use the interactive Swagger UI to try endpoints
   - Or use curl/Postman with the examples below

## API Endpoints

### Health Check

**GET** `/health`

Check if the API is running.

**Response**:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### Root Endpoint

**GET** `/`

Get API information and available endpoints.

**Response**:
```json
{
  "name": "Healthcare Denial Management API",
  "version": "0.1.0",
  "documentation": {
    "swagger_ui": "/docs",
    "redoc": "/redoc",
    "openapi_json": "/openapi.json"
  },
  "endpoints": { ... }
}
```

---

## Prediction Endpoints

### Single Prediction

**POST** `/api/v1/predict`

Predict denial probability for a single claim.

**Request Body**:
```json
{
  "claim_id": "12345",
  "practice_id": "practice-guid",
  "payer_id": "payer-guid",
  "total_billed_amount": 1000.00,
  "primary_cpt_code": "97110",
  ...
}
```

**Response**:
```json
{
  "claim_id": "12345",
  "denial_probability": 0.75,
  "risk_level": "high",
  "recommendation": "..."
}
```

### Batch Prediction

**POST** `/api/v1/predict/batch`

Predict denial probability for multiple claims.

### Model Info

**GET** `/api/v1/model/info`

Get information about the trained model.

---

## Analytics Endpoints

### Practice-Specific Analytics

#### Performance Summary

**GET** `/api/v1/analytics/practice/{practice_guid}/performance-summary?days_back=365`

Get comprehensive performance summary for a practice.

**Query Parameters**:
- `days_back` (int, default: 365): Number of days to analyze

**Response**:
```json
{
  "practice_id": "...",
  "practice_name": "Practice Name",
  "total_claims": 1000,
  "denied_claims": 650,
  "denial_rate": 0.65,
  "denied_amount": 125000.00,
  "recovery_potential": 37500.00,
  "insights": {
    "trends": {
      "avg_payment_ratio": 0.35,
      "low_payment_claims": 800,
      "low_payment_pct": 0.80
    },
    "key_issues": [
      "Very high denial rate (65.0%) - above 50%"
    ],
    "risk_factors": [
      "High denial rate with Medicare",
      "High denial rate for CPT 97110"
    ]
  }
}
```

#### Prioritized Action Items

**GET** `/api/v1/analytics/practice/{practice_guid}/action-items?days_back=365`

Get prioritized, actionable recommendations for a practice.

**Response**:
```json
{
  "practice_id": "...",
  "practice_name": "Practice Name",
  "action_items": [
    {
      "priority": "high",
      "title": "Top Denial Reason: Fee schedule exceedance (CARC 45)",
      "financial_impact": 50000.00,
      "recommendation": "Review fee schedules and contracted rates...",
      "type": "carc",
      "carc_code": 45
    },
    {
      "priority": "medium",
      "title": "CPT 97110 + Fee schedule exceedance (CARC 45)",
      "financial_impact": 25000.00,
      "recommendation": "Review CPT 97110 billing practices...",
      "type": "cpt_carc",
      "cpt_code": "97110",
      "carc_code": 45
    }
  ]
}
```

#### Payer Performance

**GET** `/api/v1/analytics/practice/{practice_guid}/payer-performance?days_back=365`

Get denial performance breakdown by payer.

**Response**:
```json
{
  "practice_id": "...",
  "practice_name": "Practice Name",
  "payers": [
    {
      "payer_name": "Medicare",
      "total_claims": 500,
      "denied_claims": 400,
      "denial_rate": 0.80,
      "denied_amount": 80000.00,
      "avg_denial_probability": 0.75
    }
  ]
}
```

#### CPT Performance

**GET** `/api/v1/analytics/practice/{practice_guid}/cpt-performance?days_back=365`

Get denial performance breakdown by CPT code.

#### High-Risk Claims

**GET** `/api/v1/analytics/practice/{practice_guid}/high-risk-claims?days_back=365&limit=20`

Get list of high-risk claims requiring immediate attention.

#### Denial Reasons (CARC/RARC)

**GET** `/api/v1/analytics/practice/{practice_guid}/denial-reasons?days_back=365`

Get analysis of denial reasons by CARC/RARC codes.

**Response**:
```json
{
  "practice_id": "...",
  "practice_name": "Practice Name",
  "carc_codes": [
    {
      "carc_code": 45,
      "description": "Charge exceeds fee schedule...",
      "occurrence_count": 500,
      "affected_claims": 450,
      "total_adjustment_amount": 50000.00
    }
  ],
  "rarc_codes": [...]
}
```

#### CPT-CARC Correlation

**GET** `/api/v1/analytics/practice/{practice_guid}/cpt-carc-correlation?days_back=365`

Get correlation analysis between CPT codes and CARC/RARC codes.

**Response**:
```json
{
  "practice_id": "...",
  "practice_name": "Practice Name",
  "cpt_carc": [
    {
      "cpt_code": "97110",
      "carc_code": 45,
      "carc_description": "Fee schedule exceedance",
      "occurrence_count": 200,
      "affected_claims": 180,
      "total_adjustment_amount": 25000.00
    }
  ],
  "cpt_rarc": [...]
}
```

#### Rejection Patterns

**GET** `/api/v1/analytics/practice/{practice_guid}/rejection-patterns?days_back=365`

Get analysis of rejection patterns and missing field issues.

**Response**:
```json
{
  "practice_id": "...",
  "practice_name": "Practice Name",
  "rejection_patterns": [
    {
      "cpt_code": "97110",
      "total_rejections": 5,
      "total_claims": 100,
      "rejection_rate": 0.05,
      "missing_submitted_date": 5,
      "missing_patient_id": 0,
      "rejection_risk_score": 20
    }
  ]
}
```

### System-Wide Analytics

#### Overall Insights

**GET** `/api/v1/analytics/overall-insights?days_back=365`

Get aggregated insights across ALL practices.

**Response**:
```json
{
  "total_practices": 14,
  "total_claims": 7848,
  "total_denials": 5168,
  "overall_denial_rate": 0.6585,
  "total_denied_amount": 2289108.69,
  "top_carc_codes": [
    {
      "carc_code": 45,
      "occurrence_count": 4551,
      "total_amount": 1456154.07
    }
  ],
  "top_payers": [
    {
      "payer_name": "Medicare of Maryland - J12",
      "total_claims": 488,
      "denied_claims": 460,
      "denial_rate": 0.9426,
      "denied_amount": 1127000.00
    }
  ],
  "top_cpt_codes": [...],
  "key_findings": [
    "Overall denial rate is very high (65.9%)",
    "Top denial reason: Fee schedule exceedance (CARC 45)",
    "Potential recovery through appeals: $686,732.61"
  ]
}
```

#### All Practices

**GET** `/api/v1/analytics/practices?days_back=365&min_claims=1`

Get list of all practices with claims.

#### All Payers

**GET** `/api/v1/analytics/payers?days_back=365&min_claims=1`

Get list of all payers with claims.

#### Practice-Payer Combinations

**GET** `/api/v1/analytics/practice-payer?days_back=365&min_claims=5`

Get analysis of practice-payer combinations.

---

## Example Usage

### Using curl

```bash
# Get performance summary
curl "http://localhost:8001/api/v1/analytics/practice/{practice_guid}/performance-summary?days_back=60"

# Get action items
curl "http://localhost:8001/api/v1/analytics/practice/{practice_guid}/action-items?days_back=60"

# Get overall insights
curl "http://localhost:8001/api/v1/analytics/overall-insights?days_back=365"
```

### Using Python requests

```python
import requests

BASE_URL = "http://localhost:8001"

# Get performance summary
response = requests.get(
    f"{BASE_URL}/api/v1/analytics/practice/{practice_guid}/performance-summary",
    params={"days_back": 60}
)
data = response.json()
print(f"Denial rate: {data['denial_rate']:.1%}")
print(f"Recovery potential: ${data['recovery_potential']:,.2f}")
```

### Using the Interactive Docs

1. Start the API server
2. Open `http://localhost:8001/docs` in your browser
3. Click on any endpoint to expand it
4. Click "Try it out" to test the endpoint
5. Fill in parameters and click "Execute"
6. See the response below

---

## Response Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found (e.g., practice not found)
- `500 Internal Server Error`: Server error (check logs)

---

## Authentication

Currently, the API does not require authentication. For production use, implement:
- API key authentication
- OAuth2/JWT tokens
- Role-based access control

---

## Rate Limiting

Currently, there are no rate limits. For production use, implement:
- Request rate limiting per IP/API key
- Concurrent request limits
- Timeout handling

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Example:
```json
{
  "detail": "No claims found for practice abc-123"
}
```

---

## Additional Documentation

- **API Enhancements**: See `API_ENHANCEMENTS.md` for recent enhancements
- **Practice Analytics**: See `PRACTICE_ANALYTICS_API.md` for detailed practice analytics documentation
- **Implementation Summary**: See `IMPLEMENTATION_SUMMARY.md` for overall system architecture

---

## Support

For issues or questions:
1. Check the interactive documentation at `/docs`
2. Review the error message in the response
3. Check server logs for detailed error information
4. Review the implementation documentation files
