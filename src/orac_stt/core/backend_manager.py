"""Backend manager for handling Home Assistant and other backend configurations."""

import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiohttp
from pydantic import BaseModel, Field


class BackendConnection(BaseModel):
    """Backend connection configuration."""
    url: str
    port: int
    token: str
    ssl_verify: bool = True
    timeout: int = 10


class BackendStatus(BaseModel):
    """Backend connection status."""
    connected: bool
    last_check: Optional[datetime] = None
    version: Optional[str] = None
    error: Optional[str] = None


class EntityConfig(BaseModel):
    """Entity configuration."""
    enabled: bool = False
    friendly_name: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    original_name: str
    domain: str
    area: Optional[str] = None
    priority: int = 5
    configured_at: Optional[datetime] = None


class BackendConfig(BaseModel):
    """Complete backend configuration."""
    id: str
    name: str
    type: str = "homeassistant"
    created_at: datetime
    updated_at: datetime
    connection: BackendConnection
    status: BackendStatus
    entities: Dict[str, EntityConfig] = Field(default_factory=dict)
    statistics: Dict[str, Any] = Field(default_factory=dict)


class BackendManager:
    """Manages backend configurations and connections."""

    def __init__(self, data_dir: Path = Path("/data/backends")):
        """Initialize backend manager.

        Args:
            data_dir: Directory for storing backend configurations
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backends: Dict[str, BackendConfig] = {}
        self._load_backends()

    def _load_backends(self):
        """Load all backend configurations from disk."""
        for config_file in self.data_dir.glob("*.json"):
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    backend = BackendConfig(**data)
                    self.backends[backend.id] = backend
            except Exception as e:
                print(f"Error loading backend {config_file}: {e}")

    def _save_backend(self, backend: BackendConfig):
        """Save backend configuration to disk.

        Args:
            backend: Backend configuration to save
        """
        config_file = self.data_dir / f"{backend.id}.json"
        with open(config_file, 'w') as f:
            json.dump(backend.model_dump(mode='json'), f, indent=2, default=str)

    async def create_backend(self, name: str, connection: BackendConnection) -> BackendConfig:
        """Create a new backend configuration.

        Args:
            name: User-friendly name for the backend
            connection: Connection configuration

        Returns:
            Created backend configuration
        """
        backend_id = f"ha_{uuid4().hex[:8]}"
        now = datetime.utcnow()

        backend = BackendConfig(
            id=backend_id,
            name=name,
            type="homeassistant",
            created_at=now,
            updated_at=now,
            connection=connection,
            status=BackendStatus(connected=False)
        )

        self.backends[backend_id] = backend
        self._save_backend(backend)

        return backend

    async def update_backend(self, backend_id: str, updates: Dict[str, Any]) -> Optional[BackendConfig]:
        """Update backend configuration.

        Args:
            backend_id: Backend identifier
            updates: Fields to update

        Returns:
            Updated backend configuration or None if not found
        """
        if backend_id not in self.backends:
            return None

        backend = self.backends[backend_id]

        # Update fields
        for key, value in updates.items():
            if hasattr(backend, key):
                setattr(backend, key, value)

        backend.updated_at = datetime.utcnow()
        self._save_backend(backend)

        return backend

    async def delete_backend(self, backend_id: str) -> bool:
        """Delete a backend configuration.

        Args:
            backend_id: Backend identifier

        Returns:
            True if deleted, False if not found
        """
        if backend_id not in self.backends:
            return False

        del self.backends[backend_id]
        config_file = self.data_dir / f"{backend_id}.json"
        if config_file.exists():
            config_file.unlink()

        return True

    async def test_connection(self, backend_id: str) -> BackendStatus:
        """Test connection to a backend.

        Args:
            backend_id: Backend identifier

        Returns:
            Connection status
        """
        if backend_id not in self.backends:
            return BackendStatus(connected=False, error="Backend not found")

        backend = self.backends[backend_id]
        connection = backend.connection

        # Build Home Assistant API URL
        base_url = f"{connection.url}:{connection.port}"
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"

        headers = {
            "Authorization": f"Bearer {connection.token}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}/api/",
                    headers=headers,
                    ssl=connection.ssl_verify,
                    timeout=aiohttp.ClientTimeout(total=connection.timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        status = BackendStatus(
                            connected=True,
                            last_check=datetime.utcnow(),
                            version=data.get("version", "Unknown"),
                            error=None
                        )
                    else:
                        status = BackendStatus(
                            connected=False,
                            last_check=datetime.utcnow(),
                            error=f"HTTP {response.status}: {await response.text()}"
                        )
        except asyncio.TimeoutError:
            status = BackendStatus(
                connected=False,
                last_check=datetime.utcnow(),
                error="Connection timeout"
            )
        except Exception as e:
            status = BackendStatus(
                connected=False,
                last_check=datetime.utcnow(),
                error=str(e)
            )

        # Update backend status
        backend.status = status
        backend.updated_at = datetime.utcnow()
        self._save_backend(backend)

        return status

    async def fetch_entities(self, backend_id: str) -> Dict[str, Any]:
        """Fetch all entities from a Home Assistant backend.

        Args:
            backend_id: Backend identifier

        Returns:
            Dictionary of entities or error information
        """
        if backend_id not in self.backends:
            return {"error": "Backend not found"}

        backend = self.backends[backend_id]
        connection = backend.connection

        # Build Home Assistant API URL
        base_url = f"{connection.url}:{connection.port}"
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"

        headers = {
            "Authorization": f"Bearer {connection.token}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{base_url}/api/states",
                    headers=headers,
                    ssl=connection.ssl_verify,
                    timeout=aiohttp.ClientTimeout(total=connection.timeout)
                ) as response:
                    if response.status == 200:
                        entities = await response.json()

                        # Process entities
                        for entity in entities:
                            entity_id = entity.get("entity_id", "")
                            if entity_id and entity_id not in backend.entities:
                                domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
                                backend.entities[entity_id] = EntityConfig(
                                    enabled=False,
                                    original_name=entity.get("attributes", {}).get("friendly_name", entity_id),
                                    domain=domain,
                                    area=entity.get("attributes", {}).get("area", None)
                                )

                        # Update statistics
                        backend.statistics = {
                            "total_entities": len(backend.entities),
                            "enabled_entities": sum(1 for e in backend.entities.values() if e.enabled),
                            "configured_entities": sum(1 for e in backend.entities.values() if e.friendly_name),
                            "last_sync": datetime.utcnow().isoformat()
                        }

                        backend.updated_at = datetime.utcnow()
                        self._save_backend(backend)

                        return {
                            "success": True,
                            "entities": {k: v.model_dump() for k, v in backend.entities.items()},
                            "statistics": backend.statistics
                        }
                    else:
                        return {"error": f"HTTP {response.status}: {await response.text()}"}
        except Exception as e:
            return {"error": str(e)}

    async def update_entity(self, backend_id: str, entity_id: str, updates: Dict[str, Any]) -> bool:
        """Update entity configuration.

        Args:
            backend_id: Backend identifier
            entity_id: Entity identifier
            updates: Fields to update

        Returns:
            True if updated, False if not found
        """
        if backend_id not in self.backends:
            return False

        backend = self.backends[backend_id]

        if entity_id not in backend.entities:
            return False

        entity = backend.entities[entity_id]

        # Update fields
        for key, value in updates.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        if updates:
            entity.configured_at = datetime.utcnow()

        # Update statistics
        backend.statistics = {
            "total_entities": len(backend.entities),
            "enabled_entities": sum(1 for e in backend.entities.values() if e.enabled),
            "configured_entities": sum(1 for e in backend.entities.values() if e.friendly_name),
            "last_sync": backend.statistics.get("last_sync", datetime.utcnow().isoformat())
        }

        backend.updated_at = datetime.utcnow()
        self._save_backend(backend)

        return True

    async def bulk_update_entities(self, backend_id: str, entity_ids: List[str], enabled: bool) -> int:
        """Bulk enable/disable entities.

        Args:
            backend_id: Backend identifier
            entity_ids: List of entity IDs
            enabled: Enable or disable entities

        Returns:
            Number of entities updated
        """
        if backend_id not in self.backends:
            return 0

        backend = self.backends[backend_id]
        updated = 0

        for entity_id in entity_ids:
            if entity_id in backend.entities:
                backend.entities[entity_id].enabled = enabled
                updated += 1

        if updated > 0:
            # Update statistics
            backend.statistics = {
                "total_entities": len(backend.entities),
                "enabled_entities": sum(1 for e in backend.entities.values() if e.enabled),
                "configured_entities": sum(1 for e in backend.entities.values() if e.friendly_name),
                "last_sync": backend.statistics.get("last_sync", datetime.utcnow().isoformat())
            }

            backend.updated_at = datetime.utcnow()
            self._save_backend(backend)

        return updated

    def get_backend(self, backend_id: str) -> Optional[BackendConfig]:
        """Get backend configuration.

        Args:
            backend_id: Backend identifier

        Returns:
            Backend configuration or None if not found
        """
        return self.backends.get(backend_id)

    def list_backends(self) -> List[BackendConfig]:
        """List all backend configurations.

        Returns:
            List of backend configurations
        """
        return list(self.backends.values())