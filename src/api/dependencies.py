"""FastAPI dependency injection.

Provides injectable dependencies for API route handlers.
"""

from src.data_access.factory import get_repository
from src.data_access.base_repository import ClaimsRepository


def get_claims_repository() -> ClaimsRepository:
    """Dependency for claims repository."""
    return get_repository()
