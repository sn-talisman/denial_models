"""Claims data ingestion pipeline.

Loads raw claims data from repository, validates schema, and prepares
for downstream processing.
"""

from typing import Optional
from datetime import date
import pandas as pd
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.pipelines.ingestion.schema_validation import validate_claims_schema

logger = structlog.get_logger(__name__)


async def ingest_claims(
    repository: ClaimsRepository,
    practice_id: Optional[str] = None,
    payer_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: Optional[int] = None,
    validate: bool = True,
) -> pd.DataFrame:
    """Ingest claims from repository and return as DataFrame.
    
    Args:
        repository: Claims repository instance
        practice_id: Optional practice filter
        payer_id: Optional payer filter
        date_from: Optional date range start
        date_to: Optional date range end
        limit: Optional limit on number of claims
        validate: Whether to validate schema
        
    Returns:
        DataFrame with claims data
        
    Raises:
        ValueError: If schema validation fails
    """
    logger.info(
        "Starting claims ingestion",
        practice_id=practice_id,
        payer_id=payer_id,
        date_from=date_from,
        date_to=date_to,
    )
    
    # Fetch claims from repository
    claims = await repository.get_claims(
        practice_id=practice_id,
        payer_id=payer_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit or 10000,
        offset=0,
    )
    
    logger.info("Fetched claims from repository", count=len(claims))
    
    if not claims:
        logger.warning("No claims found with specified filters")
        return pd.DataFrame()
    
    # Convert to DataFrame
    claims_data = [claim.model_dump() for claim in claims]
    df = pd.DataFrame(claims_data)
    
    logger.info("Converted claims to DataFrame", shape=df.shape)
    
    # Validate schema if requested
    if validate:
        try:
            validate_claims_schema(df)
            logger.info("Schema validation passed")
        except Exception as e:
            logger.error("Schema validation failed", error=str(e))
            raise ValueError(f"Schema validation failed: {e}") from e
    
    return df

