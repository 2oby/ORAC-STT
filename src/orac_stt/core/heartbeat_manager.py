"""Heartbeat manager for tracking and forwarding wake word topics."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from pathlib import Path

from ..models.heartbeat import (
    HeartbeatRequest,
    CoreHeartbeatRequest, 
    TopicHeartbeat,
    HeartbeatResponse
)
from ..utils.logging import get_logger
from ..integrations.orac_core_client import ORACCoreClient
from ..config.loader import load_config
from .topic_registry import TopicRegistry

logger = get_logger(__name__)


class HeartbeatManager:
    """Manages heartbeat tracking and forwarding to ORAC Core."""
    
    def __init__(self, ttl_seconds: int = 120, data_dir: str = "/app/data"):
        """Initialize heartbeat manager.
        
        Args:
            ttl_seconds: Time-to-live for heartbeat data (default 120s for 60s idle interval)
            data_dir: Directory for persisting topic data
        """
        self.ttl_seconds = ttl_seconds
        self._heartbeats: Dict[str, Dict] = {}  # instance_id -> heartbeat data
        self._core_client: Optional[ORACCoreClient] = None
        self._instance_id = "orac_stt_001"  # TODO: Make configurable
        self._forward_lock = asyncio.Lock()
        self._last_forward_time = datetime.min
        self._forward_interval = timedelta(seconds=5)  # Batch forwards every 5s
        self._topic_registry = TopicRegistry(data_dir=data_dir)
        
    def _get_core_client(self) -> Optional[ORACCoreClient]:
        """Get or create ORAC Core client."""
        if self._core_client is None:
            try:
                # First try to get from settings manager (runtime config)
                from ..core.settings_manager import get_settings_manager
                settings_mgr = get_settings_manager()
                core_url = settings_mgr.get('orac_core_url')
                
                # Fallback to config file
                if not core_url:
                    settings = load_config()
                    core_url = getattr(settings, 'orac_core_url', None)
                
                if core_url:
                    self._core_client = ORACCoreClient(base_url=core_url)
                    logger.info(f"Initialized ORAC Core client for heartbeat: {core_url}")
            except Exception as e:
                logger.error(f"Failed to initialize ORAC Core client: {e}")
        return self._core_client
    
    async def process_heartbeat(self, request: HeartbeatRequest) -> HeartbeatResponse:
        """Process incoming heartbeat from Hey ORAC.
        
        Args:
            request: Heartbeat request with batched models
            
        Returns:
            Response indicating processing status
        """
        try:
            # Store heartbeat data with timestamp
            self._heartbeats[request.instance_id] = {
                "source": request.source,
                "timestamp": request.timestamp,
                "models": request.models,
                "received_at": datetime.utcnow()
            }
            
            # Auto-register topics from heartbeat
            for model in request.models:
                metadata = {
                    "wake_word": model.wake_word,
                    "trigger_count": model.trigger_count,
                    "last_triggered": model.last_triggered.isoformat() if model.last_triggered else None,
                    "status": model.status
                }
                self._topic_registry.auto_register(model.topic, metadata)
            
            # Filter active models
            active_models = [m for m in request.models if m.status == "active"]
            
            logger.info(
                f"Received heartbeat from {request.instance_id}: "
                f"{len(active_models)}/{len(request.models)} active models"
            )
            
            # Forward to ORAC Core if we have active models and enough time has passed
            if active_models and self._should_forward():
                await self._forward_to_core()
            
            return HeartbeatResponse(
                status="ok",
                message=f"Processed {len(active_models)} active models",
                topics_processed=len(active_models)
            )
            
        except Exception as e:
            logger.error(f"Failed to process heartbeat: {e}")
            return HeartbeatResponse(
                status="error",
                message=str(e),
                topics_processed=0
            )
    
    def _should_forward(self) -> bool:
        """Check if enough time has passed to forward heartbeats."""
        now = datetime.utcnow()
        return (now - self._last_forward_time) >= self._forward_interval
    
    async def _forward_to_core(self):
        """Forward active topics to ORAC Core with per-topic routing."""
        async with self._forward_lock:
            try:
                # Collect all active topics from all instances
                all_topics = []
                topic_names = []
                stale_instances = []
                now = datetime.utcnow()
                
                for instance_id, data in self._heartbeats.items():
                    # Check if heartbeat is stale
                    age = (now - data["received_at"]).total_seconds()
                    if age > self.ttl_seconds:
                        stale_instances.append(instance_id)
                        continue
                    
                    # Extract active topics
                    for model in data["models"]:
                        if model.status == "active":
                            all_topics.append(TopicHeartbeat(
                                name=model.topic,
                                status="active",
                                last_triggered=model.last_triggered,
                                trigger_count=model.trigger_count,
                                wake_word=model.wake_word
                            ))
                            topic_names.append(model.topic)
                
                # Clean up stale instances
                for instance_id in stale_instances:
                    del self._heartbeats[instance_id]
                    logger.info(f"Removed stale heartbeat from {instance_id}")
                
                if not all_topics:
                    logger.debug("No active topics to forward")
                    return
                
                # Group topics by Core URL
                grouped_topics = self._topic_registry.group_by_core_url(topic_names)
                
                # Forward to each Core instance
                for core_url, topics_for_core in grouped_topics.items():
                    # Filter topics for this Core
                    topics_to_send = [t for t in all_topics if t.name in topics_for_core]
                    
                    # Get or create client for this Core URL
                    if core_url is None:
                        # Use default Core client
                        core_client = self._get_core_client()
                        if not core_client:
                            logger.debug("Default ORAC Core not configured, skipping these topics")
                            continue
                    else:
                        # Create client for override URL
                        core_client = ORACCoreClient(base_url=core_url)
                    
                    # Create batched request
                    core_request = CoreHeartbeatRequest(
                        source="orac_stt",
                        upstream_source="hey_orac",
                        instance_id=self._instance_id,
                        timestamp=datetime.utcnow(),
                        topics=topics_to_send
                    )
                    
                    # Forward to Core
                    await core_client.forward_heartbeat(core_request)
                    
                    core_desc = core_url or "default"
                    logger.info(f"Forwarded {len(topics_to_send)} topics to ORAC Core ({core_desc})")
                
                self._last_forward_time = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Failed to forward heartbeat to Core: {e}")
    
    def get_topic_registry(self) -> TopicRegistry:
        """Get the topic registry instance.
        
        Returns:
            TopicRegistry instance
        """
        return self._topic_registry
    
    def get_status(self) -> Dict:
        """Get current heartbeat status.
        
        Returns:
            Status information including active instances and topics
        """
        now = datetime.utcnow()
        status = {
            "instance_count": len(self._heartbeats),
            "instances": [],
            "total_active_topics": 0,
            "total_inactive_topics": 0,
            "registered_topics": len(self._topic_registry.get_all_topics())
        }
        
        for instance_id, data in self._heartbeats.items():
            age = (now - data["received_at"]).total_seconds()
            active_count = sum(1 for m in data["models"] if m.status == "active")
            inactive_count = len(data["models"]) - active_count
            
            status["instances"].append({
                "instance_id": instance_id,
                "source": data["source"],
                "age_seconds": age,
                "is_stale": age > self.ttl_seconds,
                "active_models": active_count,
                "inactive_models": inactive_count,
                "last_heartbeat": data["timestamp"].isoformat()
            })
            
            status["total_active_topics"] += active_count
            status["total_inactive_topics"] += inactive_count
        
        return status
    
    async def cleanup_stale(self):
        """Clean up stale heartbeat data."""
        now = datetime.utcnow()
        stale_instances = []
        
        for instance_id, data in self._heartbeats.items():
            age = (now - data["received_at"]).total_seconds()
            if age > self.ttl_seconds:
                stale_instances.append(instance_id)
        
        for instance_id in stale_instances:
            del self._heartbeats[instance_id]
            logger.info(f"Cleaned up stale heartbeat from {instance_id}")
        
        return len(stale_instances)


# Global heartbeat manager instance
_heartbeat_manager: Optional[HeartbeatManager] = None


def get_heartbeat_manager() -> HeartbeatManager:
    """Get or create the global heartbeat manager instance."""
    global _heartbeat_manager
    if _heartbeat_manager is None:
        _heartbeat_manager = HeartbeatManager()
        logger.info("Initialized heartbeat manager")
    return _heartbeat_manager