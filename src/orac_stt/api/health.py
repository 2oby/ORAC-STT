"""Health check endpoints."""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, status
from pydantic import BaseModel

from ..utils.logging import get_logger
from ..core.whisper_manager import get_whisper_manager

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
    # Check whisper-server health
    whisper_manager = get_whisper_manager()
    whisper_healthy = whisper_manager.is_healthy()
    whisper_status = whisper_manager.get_status()

    checks = {
        "api": "healthy",
        "whisper_server": "healthy" if whisper_healthy else "unhealthy",
        "whisper_restart_count": whisper_status["restart_count"],
        "whisper_consecutive_failures": whisper_status["consecutive_failures"],
        "watchdog": "running" if whisper_status["watchdog_running"] else "stopped",
    }

    # Determine overall status
    overall_status = "healthy"
    if not whisper_healthy:
        overall_status = "degraded"
    if whisper_status["consecutive_failures"] >= whisper_manager.max_consecutive_failures:
        overall_status = "unhealthy"

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