"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Check database connection, model availability, etc.
    return {"status": "ready"}

