"""API endpoints for topic management."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..core.heartbeat_manager import get_heartbeat_manager
from ..models.topic import TopicConfig
from ..utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/topics", tags=["topics"])


class TopicConfigUpdate(BaseModel):
    """Request model for updating topic configuration."""
    orac_core_url: Optional[str] = Field(None, description="Core URL override (None uses default)")
    wake_words_to_strip: Optional[str] = Field(None, description="Comma-separated wake words to strip from transcriptions")


class TopicResponse(BaseModel):
    """Response model for topic information."""
    name: str
    is_active: bool
    orac_core_url: Optional[str]
    last_seen: Optional[str]
    metadata: dict
    wake_words_to_strip: Optional[str] = None

    @classmethod
    def from_config(cls, config: TopicConfig) -> "TopicResponse":
        """Create from TopicConfig."""
        return cls(
            name=config.name,
            is_active=config.is_active,
            orac_core_url=config.orac_core_url,
            last_seen=config.last_seen.isoformat() if config.last_seen else None,
            metadata=config.metadata,
            wake_words_to_strip=config.wake_words_to_strip
        )


@router.get("", response_model=List[TopicResponse])
async def get_topics():
    """Get all registered topics with their status.
    
    Returns:
        List of all topics with activity status
    """
    try:
        manager = get_heartbeat_manager()
        registry = manager.get_topic_registry()
        topics = registry.get_all_topics()
        
        return [TopicResponse.from_config(topic) for topic in topics]
    except Exception as e:
        logger.error(f"Failed to get topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{topic_name}", response_model=TopicResponse)
async def get_topic(topic_name: str):
    """Get a specific topic configuration.
    
    Args:
        topic_name: Name of the topic
    
    Returns:
        Topic configuration and status
    """
    try:
        manager = get_heartbeat_manager()
        registry = manager.get_topic_registry()
        topic = registry.get_topic(topic_name)
        
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic '{topic_name}' not found"
            )
        
        return TopicResponse.from_config(topic)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get topic {topic_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{topic_name}/config")
async def update_topic_config(topic_name: str, config: TopicConfigUpdate):
    """Update topic configuration (Core URL and wake words).

    Args:
        topic_name: Name of the topic
        config: Configuration update

    Returns:
        Success status
    """
    try:
        manager = get_heartbeat_manager()
        registry = manager.get_topic_registry()

        # Set the Core URL (will auto-register if not exists)
        registry.set_core_url(topic_name, config.orac_core_url)

        # Set wake words to strip
        registry.set_wake_words_to_strip(topic_name, config.wake_words_to_strip)

        logger.info(f"Updated config for topic '{topic_name}': core_url={config.orac_core_url}, wake_words={config.wake_words_to_strip}")

        return {"status": "ok", "message": f"Topic '{topic_name}' configuration updated"}
    except Exception as e:
        logger.error(f"Failed to update topic config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{topic_name}/config")
async def remove_topic_config(topic_name: str):
    """Remove Core URL override for a topic (use default).
    
    Args:
        topic_name: Name of the topic
    
    Returns:
        Success status
    """
    try:
        manager = get_heartbeat_manager()
        registry = manager.get_topic_registry()
        
        # Check if topic exists
        topic = registry.get_topic(topic_name)
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic '{topic_name}' not found"
            )
        
        # Remove Core URL override (set to None)
        registry.set_core_url(topic_name, None)
        
        logger.info(f"Removed Core URL override for topic '{topic_name}'")
        
        return {"status": "ok", "message": f"Topic '{topic_name}' will use default Core URL"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove topic config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{topic_name}")
async def delete_topic(topic_name: str):
    """Delete a topic completely from the registry.
    
    Args:
        topic_name: Name of the topic to delete
    
    Returns:
        Success status
    """
    try:
        manager = get_heartbeat_manager()
        registry = manager.get_topic_registry()
        
        # Check if topic exists
        topic = registry.get_topic(topic_name)
        if not topic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic '{topic_name}' not found"
            )
        
        # Remove the topic
        success = registry.remove_topic(topic_name)
        
        if success:
            logger.info(f"Deleted topic '{topic_name}'")
            return {"status": "ok", "message": f"Topic '{topic_name}' deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete topic '{topic_name}'"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete topic {topic_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/active", response_model=List[TopicResponse])
async def get_active_topics():
    """Get only active topics (recent heartbeats).
    
    Returns:
        List of active topics
    """
    try:
        manager = get_heartbeat_manager()
        registry = manager.get_topic_registry()
        topics = registry.get_active_topics()
        
        return [TopicResponse.from_config(topic) for topic in topics]
    except Exception as e:
        logger.error(f"Failed to get active topics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )