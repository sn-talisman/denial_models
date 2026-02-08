"""Shared constants and enumerations."""

from enum import Enum


class DenialCategory(str, Enum):
    """Denial category enumeration."""
    
    ELIGIBILITY_COVERAGE = "eligibility_coverage"
    AUTHORIZATION = "authorization"
    CODING_ERRORS = "coding_errors"
    MEDICAL_NECESSITY = "medical_necessity"
    DUPLICATE_CLAIM = "duplicate_claim"
    TIMELY_FILING = "timely_filing"
    BUNDLING_UNBUNDLING = "bundling_unbundling"
    MISSING_INFORMATION = "missing_information"
    COORDINATION_OF_BENEFITS = "coordination_of_benefits"
    CONTRACTUAL = "contractual"
    OTHER = "other"


# Timely filing deadlines by payer type (days from date of service)
TIMELY_FILING_DEADLINES = {
    "medicare": 365,
    "medicaid": 365,
    "commercial": 180,
    "default": 180,
}

# Common CARC codes for quick lookup
COMMON_CARC_CODES = {
    1: "Deductible Amount",
    2: "Coinsurance Amount",
    3: "Co-payment Amount",
    4: "The procedure code is inconsistent with the modifier used or a required modifier is missing.",
    5: "The procedure code/bill type is inconsistent with the place of service.",
    6: "The procedure/revenue code is inconsistent with patient's age.",
    16: "Claim/service lacks information which is needed for adjudication.",
    18: "Exact duplicate claim/service.",
    22: "This care may be covered by another payer per coordination of benefits.",
    27: "Expenses incurred after coverage terminated.",
    29: "The time limit for filing has expired.",
    45: "Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement.",
    50: "These are non-covered services because this is not deemed a 'medical necessity' by the payer.",
    95: "Processed according to plan provisions (Plan refers to provisions that exist between the Health Plan and the patient or subscriber).",
    236: "This claim has been forwarded to entity. Note: Refer to the 835 Transaction Segment for additional information.",
    253: "Claim/service denied. Refer to the 835 Healthcare Policy Identification Segment (loop 2110 Service Payment Information REF), if present.",
}

