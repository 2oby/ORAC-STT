"""Backend management API endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..core.backend_manager import (
    BackendConfig,
    BackendConnection,
    BackendManager,
    BackendStatus
)
from ..utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Initialize backend manager
backend_manager = BackendManager()


class CreateBackendRequest(BaseModel):
    """Request model for creating a backend."""
    name: str = Field(..., description="User-friendly name for the backend")
    url: str = Field(..., description="Backend URL")
    port: int = Field(..., description="Backend port")
    token: str = Field(..., description="API token")
    ssl_verify: bool = Field(default=True, description="Verify SSL certificate")
    timeout: int = Field(default=10, description="Connection timeout in seconds")


class UpdateBackendRequest(BaseModel):
    """Request model for updating a backend."""
    name: Optional[str] = Field(None, description="User-friendly name")
    connection: Optional[BackendConnection] = Field(None, description="Connection configuration")


class UpdateEntityRequest(BaseModel):
    """Request model for updating an entity."""
    enabled: Optional[bool] = Field(None, description="Enable/disable entity")
    friendly_name: Optional[str] = Field(None, description="Friendly name for voice commands")
    aliases: Optional[List[str]] = Field(None, description="Alternative names")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Priority (1-10)")


class BulkUpdateRequest(BaseModel):
    """Request model for bulk entity updates."""
    entity_ids: List[str] = Field(..., description="List of entity IDs")
    enabled: bool = Field(..., description="Enable or disable entities")


@router.post("/api/backends", response_model=BackendConfig)
async def create_backend(request: CreateBackendRequest) -> BackendConfig:
    """Create a new backend configuration."""
    try:
        connection = BackendConnection(
            url=request.url,
            port=request.port,
            token=request.token,
            ssl_verify=request.ssl_verify,
            timeout=request.timeout
        )
        backend = await backend_manager.create_backend(request.name, connection)
        logger.info(f"Created backend: {backend.id} ({backend.name})")
        return backend
    except Exception as e:
        logger.error(f"Error creating backend: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/api/backends", response_model=List[BackendConfig])
async def list_backends() -> List[BackendConfig]:
    """List all backend configurations."""
    return backend_manager.list_backends()


@router.get("/api/backends/{backend_id}", response_model=BackendConfig)
async def get_backend(backend_id: str) -> BackendConfig:
    """Get a specific backend configuration."""
    backend = backend_manager.get_backend(backend_id)
    if not backend:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backend not found")
    return backend


@router.put("/api/backends/{backend_id}", response_model=BackendConfig)
async def update_backend(backend_id: str, request: UpdateBackendRequest) -> BackendConfig:
    """Update a backend configuration."""
    updates = request.model_dump(exclude_unset=True)
    backend = await backend_manager.update_backend(backend_id, updates)
    if not backend:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backend not found")
    logger.info(f"Updated backend: {backend_id}")
    return backend


@router.delete("/api/backends/{backend_id}")
async def delete_backend(backend_id: str) -> Dict[str, str]:
    """Delete a backend configuration."""
    if await backend_manager.delete_backend(backend_id):
        logger.info(f"Deleted backend: {backend_id}")
        return {"message": "Backend deleted successfully"}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backend not found")


@router.post("/api/backends/{backend_id}/test", response_model=BackendStatus)
async def test_connection(backend_id: str) -> BackendStatus:
    """Test backend connection."""
    status = await backend_manager.test_connection(backend_id)
    logger.info(f"Tested connection for backend {backend_id}: {status.connected}")
    return status


@router.post("/api/backends/{backend_id}/entities/fetch")
async def fetch_entities(backend_id: str) -> Dict[str, Any]:
    """Fetch all entities from a backend."""
    result = await backend_manager.fetch_entities(backend_id)
    if "error" in result:
        logger.error(f"Error fetching entities for backend {backend_id}: {result['error']}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
    logger.info(f"Fetched entities for backend {backend_id}: {result.get('statistics', {})}")
    return result


@router.get("/api/backends/{backend_id}/entities")
async def list_entities(backend_id: str) -> Dict[str, Any]:
    """List configured entities for a backend."""
    backend = backend_manager.get_backend(backend_id)
    if not backend:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backend not found")

    return {
        "entities": {k: v.model_dump() for k, v in backend.entities.items()},
        "statistics": backend.statistics
    }


@router.put("/api/backends/{backend_id}/entities/{entity_id}")
async def update_entity(
    backend_id: str,
    entity_id: str,
    request: UpdateEntityRequest
) -> Dict[str, str]:
    """Update entity configuration."""
    updates = request.model_dump(exclude_unset=True)
    if await backend_manager.update_entity(backend_id, entity_id, updates):
        logger.info(f"Updated entity {entity_id} for backend {backend_id}")
        return {"message": "Entity updated successfully"}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backend or entity not found")


@router.post("/api/backends/{backend_id}/entities/bulk")
async def bulk_update_entities(backend_id: str, request: BulkUpdateRequest) -> Dict[str, Any]:
    """Bulk enable/disable entities."""
    updated = await backend_manager.bulk_update_entities(
        backend_id,
        request.entity_ids,
        request.enabled
    )
    logger.info(f"Bulk updated {updated} entities for backend {backend_id}")
    return {
        "message": f"Updated {updated} entities",
        "updated": updated
    }


@router.get("/api/backends/{backend_id}/entities/stats")
async def get_entity_stats(backend_id: str) -> Dict[str, Any]:
    """Get entity statistics for a backend."""
    backend = backend_manager.get_backend(backend_id)
    if not backend:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backend not found")
    return backend.statistics or {}