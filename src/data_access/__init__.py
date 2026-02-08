"""Data access layer with repository pattern for claims data."""

from src.data_access.base_repository import ClaimsRepository
from src.data_access.factory import get_repository
from src.data_access.models import (
    Claim,
    ClaimLineItem,
    DenialDetail,
    Practice,
    Payer,
    Patient,
    Provider,
    DenialRateRecord,
)

__all__ = [
    "ClaimsRepository",
    "get_repository",
    "Claim",
    "ClaimLineItem",
    "DenialDetail",
    "Practice",
    "Payer",
    "Patient",
    "Provider",
    "DenialRateRecord",
]

