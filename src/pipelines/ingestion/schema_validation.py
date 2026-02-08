"""Schema validation for claims data using Pandera.

Validates that ingested claims data conforms to expected schema.
"""

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check
import structlog

logger = structlog.get_logger(__name__)


# Define claims schema
CLAIMS_SCHEMA = DataFrameSchema({
    "claim_id": Column(str, nullable=False, unique=True),
    "practice_id": Column(str, nullable=False),
    "payer_id": Column(str, nullable=False),
    "patient_id": Column(str, nullable=True),
    "provider_id": Column(str, nullable=True),
    "claim_number": Column(str, nullable=True),
    "status": Column(str, nullable=False),
    "service_date_from": Column(pd.Timestamp, nullable=True),
    "service_date_to": Column(pd.Timestamp, nullable=True),
    "submitted_date": Column(pd.Timestamp, nullable=True),
    "adjudicated_date": Column(pd.Timestamp, nullable=True),
    "total_billed_amount": Column(float, nullable=False, checks=Check.ge(0)),
    "total_allowed_amount": Column(float, nullable=True, checks=Check.ge(0)),
    "total_paid_amount": Column(float, nullable=True, checks=Check.ge(0)),
    "is_secondary_claim": Column(bool, nullable=False),
    "has_prior_auth": Column(bool, nullable=False),
    "has_referral": Column(bool, nullable=False),
    "created_at": Column(pd.Timestamp, nullable=True),
    "updated_at": Column(pd.Timestamp, nullable=True),
}, strict=True, coerce=True)


def validate_claims_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Validate claims DataFrame against schema.
    
    Args:
        df: Claims DataFrame
        
    Returns:
        Validated DataFrame (may be coerced)
        
    Raises:
        pa.errors.SchemaError: If validation fails
    """
    try:
        validated_df = CLAIMS_SCHEMA.validate(df, lazy=True)
        logger.info("Claims schema validation passed", rows=len(validated_df))
        return validated_df
    except pa.errors.SchemaErrors as e:
        logger.error(
            "Claims schema validation failed",
            errors=e.schema_errors,
            failure_cases=e.failure_cases,
        )
        raise


def validate_denial_details_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Validate denial details DataFrame.
    
    Args:
        df: Denial details DataFrame
        
    Returns:
        Validated DataFrame
        
    Raises:
        pa.errors.SchemaError: If validation fails
    """
    schema = DataFrameSchema({
        "denial_id": Column(str, nullable=False, unique=True),
        "claim_id": Column(str, nullable=False),
        "line_item_id": Column(str, nullable=True),
        "carc_code": Column(int, nullable=True),
        "rarc_code": Column(str, nullable=True),
        "remark_code": Column(str, nullable=True),
        "denial_reason_text": Column(str, nullable=True),
        "denial_category": Column(str, nullable=True),
        "denial_date": Column(pd.Timestamp, nullable=True),
        "adjustment_amount": Column(float, nullable=True),
    }, strict=True, coerce=True)
    
    try:
        validated_df = schema.validate(df, lazy=True)
        logger.info("Denial details schema validation passed", rows=len(validated_df))
        return validated_df
    except pa.errors.SchemaErrors as e:
        logger.error("Denial details schema validation failed", errors=e.schema_errors)
        raise

