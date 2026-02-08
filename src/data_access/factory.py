"""Repository factory for dependency injection.

Returns the appropriate repository implementation based on configuration.
"""

import os
from typing import Optional

import structlog

from src.data_access.base_repository import ClaimsRepository
from src.data_access.db_repository import DatabaseClaimsRepository
from src.data_access.fhir_repository import FHIRClaimsRepository

logger = structlog.get_logger(__name__)


def get_repository(repository_type: Optional[str] = None) -> ClaimsRepository:
    """Get repository instance based on configuration.
    
    Args:
        repository_type: Repository type ("database" or "fhir").
                         If None, reads from REPOSITORY_TYPE env var.
    
    Returns:
        ClaimsRepository instance
        
    Raises:
        ValueError: If repository_type is invalid
    """
    if repository_type is None:
        repository_type = os.getenv("REPOSITORY_TYPE", "database")
    
    repository_type = repository_type.lower()
    
    if repository_type == "database":
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/tebra"
        )
        logger.info("Creating database repository", type="database")
        return DatabaseClaimsRepository(database_url=database_url)
    
    elif repository_type == "fhir":
        fhir_base_url = os.getenv("FHIR_BASE_URL", "http://localhost:8080/fhir")
        logger.info("Creating FHIR repository", type="fhir", base_url=fhir_base_url)
        return FHIRClaimsRepository(fhir_base_url=fhir_base_url)
    
    else:
        raise ValueError(
            f"Invalid repository type: {repository_type}. "
            "Must be 'database' or 'fhir'"
        )

