"""Abstract base repository interface for claims data access.

This interface defines the contract that all repository implementations
must follow. This allows the system to switch between direct database
access and FHIR server access without changing pipeline or model code.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from src.data_access.models import (
    Claim,
    ClaimLineItem,
    DenialDetail,
    Practice,
    Payer,
    DenialRateRecord,
)


class ClaimsRepository(ABC):
    """Abstract interface for claims data access.
    
    All pipelines and models consume data through this interface.
    Current implementation: direct PostgreSQL access.
    Future implementation: HAPI FHIR server (R4).
    """
    
    @abstractmethod
    async def get_claims(
        self,
        practice_id: Optional[str] = None,
        payer_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status: Optional[str] = None,  # "denied", "rejected", "paid", "pending"
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[Claim]:
        """Retrieve claims with optional filters.
        
        Args:
            practice_id: Filter by practice ID
            payer_id: Filter by payer ID
            date_from: Filter claims with service date >= date_from
            date_to: Filter claims with service date <= date_to
            status: Filter by claim status
            limit: Maximum number of claims to return
            offset: Offset for pagination
            
        Returns:
            List of Claim objects
        """
        ...
    
    @abstractmethod
    async def get_claim_by_id(self, claim_id: str) -> Optional[Claim]:
        """Retrieve a single claim by ID.
        
        Args:
            claim_id: Unique claim identifier
            
        Returns:
            Claim object if found, None otherwise
        """
        ...
    
    @abstractmethod
    async def get_denial_details(self, claim_id: str) -> list[DenialDetail]:
        """Get denial/rejection reasons (CARC, RARC, remark codes) for a claim.
        
        Args:
            claim_id: Unique claim identifier
            
        Returns:
            List of DenialDetail objects
        """
        ...
    
    @abstractmethod
    async def get_practices(self) -> list[Practice]:
        """Retrieve all practices.
        
        Returns:
            List of Practice objects
        """
        ...
    
    @abstractmethod
    async def get_payers(self) -> list[Payer]:
        """Retrieve all payers.
        
        Returns:
            List of Payer objects
        """
        ...
    
    @abstractmethod
    async def get_historical_denial_rates(
        self,
        group_by: list[str],  # e.g., ["payer_id", "cpt_code"]
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list[DenialRateRecord]:
        """Aggregated denial rates for feature engineering.
        
        Args:
            group_by: List of field names to group by (e.g., ["payer_id", "cpt_code"])
            date_from: Start date for aggregation window
            date_to: End date for aggregation window
            
        Returns:
            List of DenialRateRecord objects with aggregated denial rates
        """
        ...
    
    @abstractmethod
    async def get_claim_line_items(self, claim_id: str) -> list[ClaimLineItem]:
        """Get line items for a claim.
        
        Args:
            claim_id: Unique claim identifier
            
        Returns:
            List of ClaimLineItem objects
        """
        ...
    
    @abstractmethod
    async def close(self) -> None:
        """Close repository connections and cleanup resources."""
        ...

