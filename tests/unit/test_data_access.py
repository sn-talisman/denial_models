"""Unit tests for data access layer."""

import pytest
from datetime import date

from src.data_access.models import Claim, ClaimStatus, Practice, Payer
from src.data_access.factory import get_repository


@pytest.mark.asyncio
async def test_repository_factory():
    """Test repository factory returns correct implementation."""
    repo = get_repository("database")
    assert repo is not None
    await repo.close()


@pytest.mark.asyncio
async def test_get_practices_stub():
    """Test get_practices method (stub implementation)."""
    repo = get_repository("database")
    practices = await repo.get_practices()
    # Currently returns empty list (stub)
    assert isinstance(practices, list)
    await repo.close()


@pytest.mark.asyncio
async def test_get_payers_stub():
    """Test get_payers method (stub implementation)."""
    repo = get_repository("database")
    payers = await repo.get_payers()
    # Currently returns empty list (stub)
    assert isinstance(payers, list)
    await repo.close()


def test_claim_model():
    """Test Claim Pydantic model."""
    claim = Claim(
        claim_id="test-123",
        practice_id="practice-1",
        payer_id="payer-1",
        status=ClaimStatus.PENDING,
        total_billed_amount=100.0,
    )
    assert claim.claim_id == "test-123"
    assert claim.status == ClaimStatus.PENDING


def test_practice_model():
    """Test Practice Pydantic model."""
    practice = Practice(
        practice_id="practice-1",
        name="Test Practice",
    )
    assert practice.practice_id == "practice-1"
    assert practice.name == "Test Practice"

