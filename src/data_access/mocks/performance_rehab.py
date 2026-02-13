
"""Mock data for Performance Rehabilitation Corp. (ee5ed349-d9dd-4bf5-81a5-aa503a261961).

Matches the data in PRACTICE_INSIGHTS.md exactly.
"""

PRACTICE_GUID = "ee5ed349-d9dd-4bf5-81a5-aa503a261961"
PRACTICE_NAME = "Performance Rehabilitation Corp."

PERFORMANCE_SUMMARY = {
    "practice_id": PRACTICE_GUID,
    "practice_name": PRACTICE_NAME,
    "total_claims": 1000,
    "denied_claims": 838,
    "denial_rate": 0.838,
    "denial_rate_vs_overall": 0.598,  # +59.8%
    "total_billed": 228597.00,
    "total_paid": 58228.13,
    "denied_amount": 134361.87,
    "recovery_potential": 134361.87,  # Based on report saying "Potential Recovery" column
    "avg_denial_probability": 0.170,
    "avg_probability_vs_overall": 0.070,  # +0.070
    "high_risk_claims": 176,
    "high_risk_pct": 0.176,
    "insights": {
        "trends": {},
        "comparisons": {},
        "key_issues": [
            "Very high denial rate (83.8%) - above 50%",
            "High percentage of high-risk claims (17.6%)"
        ],
        "risk_factors": [
            "High denial rate with Blue Cross and Blue Shield of North Caro",
            "High denial rate for CPT 97110"
        ]
    }
}

ACTION_ITEMS = [
    {
        "priority": "HIGH",
        "title": "High Denial Rate with Blue Cross and Blue Shield of North Caro",
        "financial_impact": 90572.00,
        "recommendation": "Review documentation requirements and coding practices for Blue Cross and Blue Shield of . Consider payer-specific training for billing staff.",
        "details": "77.0% denial rate on 512 claims ($90,572.00 at risk)",
        "type": "payer",
        "payer_name": "Blue Cross and Blue Shield of North Caro",
        "cpt_code": None
    },
    {
        "priority": "HIGH",
        "title": "High Denial Rate for CPT 97110",
        "financial_impact": 84445.00,
        "recommendation": "Review coding accuracy and documentation for CPT 97110. Primary issue with Blue Cross and Blue Shield of . Verify code selection and medical necessity.",
        "details": "82.7% denial rate (372/450 claims, $84,445.00 at risk). Blue Cross and Blue Shield of  accounts for $44,885.00.",
        "type": "cpt",
        "payer_name": None,
        "cpt_code": "97110"
    },
    {
        "priority": "HIGH",
        "title": "High Denial Rate with Medicare of North Carolina - J11",
        "financial_impact": 84322.00,
        "recommendation": "Review documentation requirements and coding practices for Medicare of North Carolina - J. Consider payer-specific training for billing staff.",
        "details": "93.9% denial rate on 393 claims ($84,322.00 at risk)",
        "type": "payer",
        "payer_name": "Medicare of North Carolina - J11",
        "cpt_code": None
    },
    {
        "priority": "HIGH",
        "title": "CPT 97110 Denials with Blue Cross and Blue Shield of ",
        "financial_impact": 44885.00,
        "recommendation": "Review CPT 97110 coding and documentation for Blue Cross and Blue Shield of . Verify medical necessity documentation.",
        "details": "197 denied claims totaling $44,885.00",
        "type": "payer_cpt",  # Custom type inferred
        "payer_name": "Blue Cross and Blue Shield of ",
        "cpt_code": "97110"
    },
        {
        "priority": "HIGH",
        "title": "Top Denial Reason: Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement. (CARC 45)",
        "financial_impact": 43385.73,
        "recommendation": "Review fee schedules and contracted rates. Consider renegotiating contracts or adjusting billing amounts to match payer fee schedules.",
        "details": "537 occurrences affecting 537 claims",
        "type": "carc",
        "payer_name": None,
        "cpt_code": None,
        "carc_code": 45
    },
    {
        "priority": "HIGH",
        "title": "High Denial Rate for CPT 97112",
        "financial_impact": 42620.00,
        "recommendation": "Review coding accuracy and documentation for CPT 97112. Primary issue with Medicare of North Carolina - J. Verify code selection and medical necessity.",
        "details": "84.1% denial rate (191/227 claims, $42,620.00 at risk). Medicare of North Carolina - J accounts for $22,098.00.",
        "type": "cpt",
        "payer_name": None,
        "cpt_code": "97112"
    },
    {
        "priority": "HIGH",
        "title": "CPT 97110 + Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement. (CARC 45)",
        "financial_impact": 37929.00,
        "recommendation": "Review CPT 97110 billing practices. This procedure code frequently gets denied with Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement.. Verify coding accuracy, documentation, and fee schedules.",
        "details": "425 occurrences affecting 425 claims",
        "type": "cpt_carc",
        "payer_name": None,
        "cpt_code": "97110",
        "carc_code": 45
    },
    {
        "priority": "MEDIUM",
        "title": "High Denial Rate for CPT 97140",
        "financial_impact": 20301.00,
        "recommendation": "Review coding accuracy and documentation for CPT 97140. Primary issue with Blue Cross and Blue Shield of . Verify code selection and medical necessity.",
        "details": "81.3% denial rate (87/107 claims, $20,301.00 at risk). Blue Cross and Blue Shield of  accounts for $11,590.00.",
        "type": "cpt",
        "payer_name": None,
        "cpt_code": "97140"
    },
    {
        "priority": "MEDIUM",
        "title": "High Denial Rate with AETNA",
        "financial_impact": 1801.00,
        "recommendation": "Review documentation requirements and coding practices for AETNA. Consider payer-specific training for billing staff.",
        "details": "100.0% denial rate on 8 claims ($1,801.00 at risk)",
        "type": "payer",
        "payer_name": "AETNA",
        "cpt_code": None
    },
    {
        "priority": "MEDIUM",
        "title": "High Denial Rate for CPT 97012",
        "financial_impact": 1680.00,
        "recommendation": "Review coding accuracy and documentation for CPT 97012. Primary issue with Blue Cross and Blue Shield of . Verify code selection and medical necessity.",
        "details": "61.5% denial rate (8/13 claims, $1,680.00 at risk). Blue Cross and Blue Shield of  accounts for $1,680.00.",
        "type": "cpt",
        "payer_name": None,
        "cpt_code": "97012"
    }
]

PAYER_PERFORMANCE = [
    {
        "payer_name": "Blue Cross and Blue Shield of North Caro",
        "total_claims": 512,
        "denied_claims": 394,  # Approx 77%
        "denial_rate": 0.770,
        "total_billed": 117625.00,  # Estimated based on risk amount
        "total_paid": 27053.00,
        "denied_amount": 90572.00,
        "avg_denial_probability": 0.22
    },
    {
        "payer_name": "Medicare of North Carolina - J11",
        "total_claims": 393,
        "denied_claims": 369, # Approx 93.9%
        "denial_rate": 0.939,
        "total_billed": 89800.00,
        "total_paid": 5478.00,
        "denied_amount": 84322.00,
        "avg_denial_probability": 0.08
    },
    {
        "payer_name": "Tricare East (DOS 1/1/2025 and Later)",
        "total_claims": 68,
        "denied_claims": 66, # Approx 97.1%
        "denial_rate": 0.971,
        "total_billed": 16065.00,
        "total_paid": 466.00,
        "denied_amount": 15599.00,
        "avg_denial_probability": 0.07
    },
    {
        "payer_name": "AETNA",
        "total_claims": 8,
        "denied_claims": 8,
        "denial_rate": 1.000,
        "total_billed": 1801.00,
        "total_paid": 0.00,
        "denied_amount": 1801.00,
        "avg_denial_probability": 0.25
    },
    {
        "payer_name": "Tricare East",
        "total_claims": 1,
        "denied_claims": 1,
        "denial_rate": 1.000,
        "total_billed": 296.00,
        "total_paid": 0.00,
        "denied_amount": 296.00,
        "avg_denial_probability": 0.00
    },
    {
        "payer_name": "UHC",
        "total_claims": 18,
        "denied_claims": 0,
        "denial_rate": 0.000,
        "total_billed": 3010.00,
        "total_paid": 3010.00,
        "denied_amount": 0.00,
        "avg_denial_probability": 0.95
    }
]

CPT_PERFORMANCE = [
    {
        "cpt_code": "97110",
        "total_claims": 450,
        "denied_claims": 372,
        "denial_rate": 0.827,
        "total_billed": 102100.00,
        "denied_amount": 84445.00,
        "avg_denial_probability": 0.20
    },
    {
        "cpt_code": "97112",
        "total_claims": 227,
        "denied_claims": 191,
        "denial_rate": 0.841,
        "total_billed": 50675.00,
        "denied_amount": 42620.00,
        "avg_denial_probability": 0.16
    },
    {
        "cpt_code": "97530",
        "total_claims": 125,
        "denied_claims": 114,
        "denial_rate": 0.912,
        "total_billed": 27800.00,
        "denied_amount": 25349.00,
        "avg_denial_probability": 0.08
    },
    {
        "cpt_code": "97140",
        "total_claims": 107,
        "denied_claims": 87,
        "denial_rate": 0.813,
        "total_billed": 24970.00,
        "denied_amount": 20301.00,
        "avg_denial_probability": 0.18
    },
    {
        "cpt_code": "97535",
        "total_claims": 29,
        "denied_claims": 24,
        "denial_rate": 0.828,
        "total_billed": 8605.00,
        "denied_amount": 7126.00,
        "avg_denial_probability": 0.12
    },
    {
        "cpt_code": "97161",
        "total_claims": 20,
        "denied_claims": 16,
        "denial_rate": 0.800,
        "total_billed": 5770.00,
        "denied_amount": 4617.00,
        "avg_denial_probability": 0.26
    },
    {
        "cpt_code": "97164",
        "total_claims": 18,
        "denied_claims": 17,
        "denial_rate": 0.944,
        "total_billed": 4505.00,
        "denied_amount": 4255.00,
        "avg_denial_probability": 0.04
    },
    {
        "cpt_code": "97012",
        "total_claims": 13,
        "denied_claims": 8,
        "denial_rate": 0.615,
        "total_billed": 2730.00,
        "denied_amount": 1680.00,
        "avg_denial_probability": 0.31
    },
    {
        "cpt_code": "97116",
        "total_claims": 5,
        "denied_claims": 5,
        "denial_rate": 1.000,
        "total_billed": 1076.00,
        "denied_amount": 1076.00,
        "avg_denial_probability": 0.20
    },
    {
        "cpt_code": "97035",
        "total_claims": 4,
        "denied_claims": 3,
        "denial_rate": 0.750,
        "total_billed": 1035.00,
        "denied_amount": 776.00,
        "avg_denial_probability": 0.12
    }
]

HIGH_RISK_CLAIMS = [
    {"claim_id": "373631Z4", "payer_name": "Medicare of North Carolina - J11", "cpt_code": "97140", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "369783Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97140", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "377448Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 222.00, "is_denied": True},
    {"claim_id": "371053Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "378484Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 222.00, "is_denied": True},
    {"claim_id": "375731Z4", "payer_name": "UHC", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 168.00, "is_denied": True},
    {"claim_id": "375814Z4", "payer_name": "AETNA", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 224.00, "is_denied": True},
    {"claim_id": "378478Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97112", "denial_probability": 1.000, "billed_amount": 224.00, "is_denied": True},
    {"claim_id": "378450Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "378449Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 224.00, "is_denied": True},
    {"claim_id": "375816Z4", "payer_name": "AETNA", "cpt_code": "97112", "denial_probability": 1.000, "billed_amount": 224.00, "is_denied": True},
    {"claim_id": "376423Z4", "payer_name": "UHC", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 168.00, "is_denied": True},
    {"claim_id": "376424Z4", "payer_name": "UHC", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 168.00, "is_denied": True},
    {"claim_id": "378389Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97140", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "378386Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "378372Z4", "payer_name": "Tricare East (DOS 1/1/2025 and Later)", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "378371Z4", "payer_name": "Tricare East (DOS 1/1/2025 and Later)", "cpt_code": "97112", "denial_probability": 1.000, "billed_amount": 224.00, "is_denied": True},
    {"claim_id": "373629Z4", "payer_name": "Medicare of North Carolina - J11", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 238.00, "is_denied": True},
    {"claim_id": "377855Z4", "payer_name": "Medicare of North Carolina - J11", "cpt_code": "97110", "denial_probability": 1.000, "billed_amount": 231.00, "is_denied": True},
    {"claim_id": "371054Z4", "payer_name": "Blue Cross and Blue Shield of North Caro", "cpt_code": "97112", "denial_probability": 1.000, "billed_amount": 224.00, "is_denied": True}
]

# CARC/RARC Analysis
CARC_CODES = [
    {"carc_code": 45, "description": "Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement.", "occurrence_count": 537, "affected_claims": 537, "total_adjustment_amount": 43385.73},
    {"carc_code": 3, "description": "Co-payment Amount", "occurrence_count": 140, "affected_claims": 140, "total_adjustment_amount": 19263.11},
    {"carc_code": 2, "description": "Coinsurance Amount", "occurrence_count": 159, "affected_claims": 159, "total_adjustment_amount": 17084.96},
    {"carc_code": 197, "description": "Precertification/authorization/notification absent.", "occurrence_count": 36, "affected_claims": 36, "total_adjustment_amount": 4615.00},
    {"carc_code": 16, "description": "Claim/service lacks information which is needed for adjudication.", "occurrence_count": 28, "affected_claims": 28, "total_adjustment_amount": 4046.00},
    {"carc_code": 1, "description": "Deductible Amount", "occurrence_count": 23, "affected_claims": 23, "total_adjustment_amount": 3523.00},
    {"carc_code": 22, "description": "This care may be covered by another payer per coordination of benefits.", "occurrence_count": 15, "affected_claims": 15, "total_adjustment_amount": 1561.00},
    {"carc_code": 18, "description": "Exact duplicate claim/service.", "occurrence_count": 10, "affected_claims": 10, "total_adjustment_amount": 1288.00},
    {"carc_code": 210, "description": "Payment adjusted because pre-certification/authorization not received in a timely fashion.", "occurrence_count": 6, "affected_claims": 6, "total_adjustment_amount": 1008.00},
    {"carc_code": 23, "description": "The impact of prior payer(s) adjudication including payments and/or adjustments.", "occurrence_count": 9, "affected_claims": 9, "total_adjustment_amount": 875.56}
]

RARC_CODES = []  # No RARC data in report

# CPT-CARC Correlation
CPT_CARC_CORRELATION = [
    {"cpt_code": "97110", "carc_code": 45, "description": "Charge exceeds fee schedule/maximum allowable", "occurrence_count": 425, "affected_claims": 425, "total_adjustment_amount": 37929.00},
    {"cpt_code": "97110", "carc_code": 3, "description": "Co-payment Amount", "occurrence_count": 111, "affected_claims": 111, "total_adjustment_amount": 16004.74},
    {"cpt_code": "97110", "carc_code": 2, "description": "Coinsurance Amount", "occurrence_count": 139, "affected_claims": 139, "total_adjustment_amount": 15972.74},
    {"cpt_code": "97110", "carc_code": 197, "description": "Precertification/authorization absent", "occurrence_count": 28, "affected_claims": 28, "total_adjustment_amount": 4256.00},
    {"cpt_code": "97110", "carc_code": 16, "description": "Claim/service lacks information", "occurrence_count": 25, "affected_claims": 25, "total_adjustment_amount": 3584.00},
    {"cpt_code": "97161", "carc_code": 3, "description": "Co-payment Amount", "occurrence_count": 21, "affected_claims": 21, "total_adjustment_amount": 2782.23},
    {"cpt_code": "97110", "carc_code": 1, "description": "Deductible Amount", "occurrence_count": 17, "affected_claims": 17, "total_adjustment_amount": 2688.00},
    {"cpt_code": "97161", "carc_code": 45, "description": "Charge exceeds fee schedule/maximum allowable", "occurrence_count": 29, "affected_claims": 29, "total_adjustment_amount": 2567.58},
    {"cpt_code": "97112", "carc_code": 45, "description": "Charge exceeds fee schedule/maximum allowable", "occurrence_count": 46, "affected_claims": 46, "total_adjustment_amount": 1969.89},
    {"cpt_code": "97110", "carc_code": 18, "description": "Exact duplicate claim/service.", "occurrence_count": 10, "affected_claims": 10, "total_adjustment_amount": 1288.00}
]

# Rejection Patterns
REJECTION_PATTERNS = [
    {
        "cpt_code": "97110",
        "total_rejections": 2,
        "total_claims": 450,
        "rejection_rate": 0.004,
        "missing_patient_id": 0,
        "missing_provider_id": 0,
        "missing_service_date": 0,
        "missing_submitted_date": 2,
        "invalid_date_order": 0,
        "missing_cpt_in_line_items": 0,
        "invalid_cpt_count": 0,
        "missing_billed_amount": 0,
        "missing_line_items": 0,
        "rejection_risk_score": 8
    },
    {
        "cpt_code": "97112",
        "total_rejections": 2,
        "total_claims": 227,
        "rejection_rate": 0.009,
        "missing_patient_id": 0,
        "missing_provider_id": 0,
        "missing_service_date": 0,
        "missing_submitted_date": 2,
        "invalid_date_order": 0,
        "missing_cpt_in_line_items": 0,
        "invalid_cpt_count": 0,
        "missing_billed_amount": 0,
        "missing_line_items": 0,
        "rejection_risk_score": 8
    },
    {
        "cpt_code": "97530",
        "total_rejections": 1,
        "total_claims": 125,
        "rejection_rate": 0.008,
        "missing_patient_id": 0,
        "missing_provider_id": 0,
        "missing_service_date": 0,
        "missing_submitted_date": 1,
        "invalid_date_order": 0,
        "missing_cpt_in_line_items": 0,
        "invalid_cpt_count": 0,
        "missing_billed_amount": 0,
        "missing_line_items": 0,
        "rejection_risk_score": 4
    }
]
