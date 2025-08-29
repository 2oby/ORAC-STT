"""Heartbeat models for Hey ORAC integration."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional


class ModelHeartbeat(BaseModel):
    """Individual wake word model heartbeat data."""
    topic: str = Field(..., description="Topic name (e.g., 'jarvis', 'friday')")
    wake_word: str = Field(..., description="Wake word phrase (e.g., 'Hey Jarvis')")
    status: str = Field(..., description="Model status: 'active' or 'inactive'")
    last_triggered: Optional[datetime] = Field(None, description="Last trigger timestamp")
    trigger_count: int = Field(0, description="Total trigger count")


class HeartbeatRequest(BaseModel):
    """Batched heartbeat request from Hey ORAC instance."""
    source: str = Field(..., description="Source identifier (e.g., 'hey_orac')")
    instance_id: str = Field(..., description="Unique instance identifier")
    timestamp: datetime = Field(..., description="Heartbeat timestamp")
    models: List[ModelHeartbeat] = Field(..., description="All models from this instance")


class TopicHeartbeat(BaseModel):
    """Topic heartbeat data for forwarding to ORAC Core."""
    name: str = Field(..., description="Topic name")
    status: str = Field(..., description="Topic status")
    last_triggered: Optional[datetime] = Field(None, description="Last trigger timestamp")
    trigger_count: int = Field(0, description="Total trigger count")
    wake_word: str = Field(..., description="Associated wake word")


class CoreHeartbeatRequest(BaseModel):
    """Batched heartbeat request to forward to ORAC Core."""
    source: str = Field("orac_stt", description="Source identifier")
    upstream_source: str = Field(..., description="Original source (e.g., 'hey_orac')")
    instance_id: str = Field(..., description="ORAC STT instance identifier")
    timestamp: datetime = Field(..., description="Forwarding timestamp")
    topics: List[TopicHeartbeat] = Field(..., description="Active topics only")


class HeartbeatResponse(BaseModel):
    """Response for heartbeat requests."""
    status: str = Field("ok", description="Response status")
    message: Optional[str] = Field(None, description="Optional status message")
    topics_processed: int = Field(0, description="Number of topics processed")