"""Topic models for ORAC STT."""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TopicConfig(BaseModel):
    """Configuration for a single topic."""
    
    name: str = Field(..., description="Topic identifier from wake word")
    orac_core_url: Optional[str] = Field(None, description="Override Core URL, None uses default")
    last_seen: Optional[datetime] = Field(None, description="Last heartbeat timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Wake word and trigger info")
    
    @property
    def is_active(self) -> bool:
        """Check if topic is active (heartbeat within last 2 minutes)."""
        if not self.last_seen:
            return False
        # Make both datetimes timezone-aware for comparison
        now = datetime.now(timezone.utc)
        last_seen = self.last_seen if self.last_seen.tzinfo else self.last_seen.replace(tzinfo=timezone.utc)
        return (now - last_seen).total_seconds() < 120

    def update_activity(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update last seen timestamp and optional metadata."""
        self.last_seen = datetime.now(timezone.utc)
        if metadata:
            self.metadata.update(metadata)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }