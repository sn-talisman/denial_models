# API Enhancements - Enhanced Insights

## Summary

Enhanced the analytics APIs to provide more comprehensive insights based on the denial and rejection pattern analyses across all practices.

## Enhanced Endpoints

### 1. Performance Summary (`/api/v1/analytics/practice/{practice_guid}/performance-summary`)

**New Fields Added:**
- `recovery_potential`: Estimated recovery amount through appeals (30% of denied amount)
- `insights`: Object containing:
  - `trends`: Payment ratio trends and low payment claim statistics
  - `comparisons`: Practice comparisons (for future use)
  - `key_issues`: List of key issues identified (e.g., "Very high denial rate")
  - `risk_factors`: List of high-risk payers and CPT codes

**Example Response:**
```json
{
  "practice_id": "...",
  "practice_name": "PERFORMANCE REHABILITATION CORP.",
  "total_claims": 229,
  "denied_claims": 180,
  "denial_rate": 0.786,
  "denied_amount": 28732.99,
  "recovery_potential": 8619.90,
  "insights": {
    "trends": {
      "avg_payment_ratio": 0.24,
      "low_payment_claims": 228,
      "low_payment_pct": 0.996
    },
    "key_issues": [
      "Very high denial rate (78.6%) - above 50%"
    ],
    "risk_factors": [
      "High denial rate with Blue Cross and Blue Shield of North Carolina",
      "High denial rate for CPT 97110"
    ]
  }
}
```

### 2. Action Items (`/api/v1/analytics/practice/{practice_guid}/action-items`)

**Enhanced Features:**
- Now includes **CARC code insights** - identifies top denial reasons with specific recommendations
- Now includes **CPT-CARC correlations** - shows which procedure codes get denied with which reasons
- Increased from 10 to 15 action items
- New `carc_code` field in action items

**New Action Item Types:**
1. **CARC-based**: Identifies top denial reason (e.g., CARC 45 - Fee schedule exceedance)
   - Provides specific recommendations based on CARC code
   - Shows financial impact and occurrence count

2. **CPT-CARC correlation**: Shows procedure-denial reason combinations
   - Example: "CPT 97110 + CARC 45" - Physical therapy frequently denied for fee schedule
   - Provides targeted recommendations for specific procedure codes

**Example Response:**
```json
{
  "action_items": [
    {
      "priority": "high",
      "title": "Top Denial Reason: Charge exceeds fee schedule (CARC 45)",
      "financial_impact": 12744.32,
      "recommendation": "Review fee schedules and contracted rates. Consider renegotiating contracts...",
      "type": "carc",
      "carc_code": 45
    },
    {
      "priority": "medium",
      "title": "CPT 97110 + Charge exceeds fee schedule (CARC 45)",
      "financial_impact": 11688.17,
      "recommendation": "Review CPT 97110 billing practices. This procedure code frequently gets denied...",
      "type": "cpt_carc",
      "cpt_code": "97110",
      "carc_code": 45
    }
  ]
}
```

### 3. New Endpoint: Overall Insights (`/api/v1/analytics/overall-insights`)

**Purpose**: Provides aggregated insights across ALL practices in the system.

**Response Fields:**
- `total_practices`: Number of practices analyzed
- `total_claims`: Total claims across all practices
- `total_denials`: Total denials across all practices
- `overall_denial_rate`: System-wide denial rate
- `total_denied_amount`: Total financial impact
- `top_carc_codes`: Top 10 CARC codes across all practices
- `top_payers`: Top 10 payers by denial amount
- `top_cpt_codes`: Top 10 CPT codes by denial amount
- `key_findings`: List of key insights and recommendations

**Use Cases:**
- System-wide health monitoring
- Identifying common issues across practices
- Prioritizing system-wide improvements
- Executive dashboards

**Example Response:**
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
  "key_findings": [
    "Overall denial rate is very high (65.9%)",
    "Top denial reason: Charge exceeds fee schedule (CARC 45) ($1,456,154.07)",
    "Potential recovery through appeals: $686,732.61 (30% recovery rate)"
  ]
}
```

## Enhanced Insights Logic

### CARC Code Recommendations

The system now provides specific recommendations based on CARC codes:

- **CARC 45** (Fee schedule exceedance): "Review fee schedules and contracted rates. Consider renegotiating contracts or adjusting billing amounts to match payer fee schedules."
- **CARC 16** (Missing information): "Improve claim documentation completeness. Ensure all required information is included before submission."
- **CARC 50-59** (Medical necessity): "Review medical necessity documentation. Ensure proper documentation supports the medical necessity of services."
- **CARC 29** (Timely filing): "Improve timely filing processes. Submit claims within payer-specific deadlines."

### Risk Factor Identification

The system automatically identifies:
- **High-risk payers**: Payers with denial rates > 50%
- **High-risk CPT codes**: Procedure codes with denial rates > 50%
- **Payment ratio issues**: Claims with payment ratio < 50%

### Financial Impact Analysis

- **Recovery Potential**: Calculates potential recovery through appeals (30% recovery rate assumption)
- **Denied Amount**: Shows actual denied amount (including partial denials)
- **Prioritization**: Action items sorted by financial impact

## Benefits

1. **More Actionable Insights**: CARC code and CPT-CARC correlation insights provide specific, targeted recommendations
2. **Better Prioritization**: Financial impact and recovery potential help prioritize efforts
3. **System-Wide View**: Overall insights endpoint provides executive-level visibility
4. **Risk Identification**: Automatic identification of high-risk payers and CPT codes
5. **Trend Analysis**: Payment ratio trends help identify systemic issues

## Usage Examples

### Get Enhanced Performance Summary
```bash
curl "http://localhost:8001/api/v1/analytics/practice/{practice_guid}/performance-summary?days_back=60"
```

### Get Enhanced Action Items (now includes CARC insights)
```bash
curl "http://localhost:8001/api/v1/analytics/practice/{practice_guid}/action-items?days_back=60"
```

### Get Overall System Insights
```bash
curl "http://localhost:8001/api/v1/analytics/overall-insights?days_back=365"
```

## Next Steps

Potential future enhancements:
1. Historical trend analysis (denial rates over time)
2. Predictive insights (forecasting future denials)
3. Comparative benchmarking (practice vs. practice)
4. Automated alerting for high-risk patterns
5. Integration with appeal workflow systems

