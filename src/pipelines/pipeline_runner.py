"""Pipeline orchestrator.

Coordinates the full data processing pipeline:
ingest → normalize → featurize (future)
"""

from typing import Optional
from datetime import date
import pandas as pd
import structlog

from src.data_access.base_repository import ClaimsRepository
from src.pipelines.ingestion.claims_ingestion import ingest_claims
from src.pipelines.normalization.denial_taxonomy import DenialTaxonomyNormalizer
from src.pipelines.feature_engineering.feature_engineer_optimized import engineer_features_batch_optimized

logger = structlog.get_logger(__name__)


class PipelineRunner:
    """Orchestrates the full data processing pipeline."""
    
    def __init__(self, repository: ClaimsRepository):
        """Initialize pipeline runner.
        
        Args:
            repository: Claims repository instance
        """
        self.repository = repository
        self.taxonomy_normalizer = DenialTaxonomyNormalizer()
        logger.info("Pipeline runner initialized")
    
    async def run_full_pipeline(
        self,
        practice_id: Optional[str] = None,
        payer_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: Optional[int] = None,
        include_features: bool = True,
    ) -> pd.DataFrame:
        """Run full pipeline: ingest → normalize → featurize.
        
        Args:
            practice_id: Optional practice filter
            payer_id: Optional payer filter
            date_from: Optional date range start
            date_to: Optional date range end
            limit: Optional limit on number of claims
            include_features: Whether to engineer features (default True)
            
        Returns:
            Processed DataFrame with features (if include_features=True) or raw claims
        """
        logger.info("Starting full pipeline", 
                   practice_id=practice_id, 
                   payer_id=payer_id,
                   include_features=include_features)
        
        # Step 1: Ingest
        claims = await self.repository.get_claims(
            practice_id=practice_id,
            payer_id=payer_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        
        if not claims:
            logger.warning("No claims to process")
            return pd.DataFrame()
        
        logger.info("Ingested claims", count=len(claims))
        
        # Step 2: Feature engineering (if requested)
        if include_features:
            # Use optimized feature engineering which includes:
            # - CPT-CARC/RARC interaction features (for denials)
            # - Rejection pattern features (for rejections)
            df = await engineer_features_batch_optimized(
                claims=claims,
                repository=self.repository,
                reference_date=date_to or date.today(),
            )
            logger.info("Pipeline completed with features", 
                       rows=len(df),
                       features=len(df.columns) if not df.empty else 0)
        else:
            # Convert claims to DataFrame without features
            import pandas as pd
            df = pd.DataFrame([c.model_dump() for c in claims])
            logger.info("Pipeline completed without features", rows=len(df))
        
        return df

