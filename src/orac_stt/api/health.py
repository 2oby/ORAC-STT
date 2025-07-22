"""Health check endpoints."""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, status
from pydantic import BaseModel

from ..utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class HealthStatus(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    checks: Dict[str, Any]


@router.get(
    "/health",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Check if the service is healthy and ready to accept requests"
)
async def health_check() -> HealthStatus:
    """Perform health check and return service status."""
    checks = {
        "api": "healthy",
        "model": "not_loaded",  # Will be updated when model is implemented
        "gpu": "not_checked",  # Will be updated when GPU check is implemented
    }
    
    # Determine overall status
    overall_status = "healthy"
    if any(status == "unhealthy" for status in checks.values()):
        overall_status = "unhealthy"
    elif any(status in ["not_loaded", "not_checked"] for status in checks.values()):
        overall_status = "degraded"
    
    return HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="0.1.0",
        checks=checks
    )


@router.get(
    "/health/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Simple liveness check for Kubernetes"
)
async def liveness():
    """Simple liveness probe."""
    return {"status": "alive"}


@router.get(
    "/health/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    description="Check if service is ready to accept traffic"
)
async def readiness():
    """Readiness probe for Kubernetes."""
    # TODO: Check if model is loaded and ready
    return {"status": "ready"}