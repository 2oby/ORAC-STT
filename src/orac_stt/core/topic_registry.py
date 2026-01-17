"""Topic registry for lazy registration and management."""
import os
import yaml
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from threading import RLock

from ..models.topic import TopicConfig

logger = logging.getLogger(__name__)


class TopicRegistry:
    """Registry for managing topics with lazy registration from heartbeats."""
    
    def __init__(self, data_dir: str = "/app/data"):
        """Initialize topic registry.
        
        Args:
            data_dir: Directory for persisting topic data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.topics_file = self.data_dir / "topics.yaml"
        self.topics: Dict[str, TopicConfig] = {}
        self._lock = RLock()
        self.load()
    
    def auto_register(self, topic_name: str, metadata: Optional[Dict[str, Any]] = None) -> TopicConfig:
        """Auto-register a topic from heartbeat (lazy creation).
        
        Args:
            topic_name: Name of the topic (from wake word)
            metadata: Optional metadata (wake_word, trigger_count, etc.)
        
        Returns:
            TopicConfig instance (new or existing)
        """
        with self._lock:
            if topic_name not in self.topics:
                logger.info(f"Auto-registering new topic: {topic_name}")
                topic = TopicConfig(
                    name=topic_name,
                    last_seen=datetime.now(timezone.utc),
                    metadata=metadata or {}
                )
                self.topics[topic_name] = topic
                self.save()
            else:
                topic = self.topics[topic_name]
                topic.update_activity(metadata)
            
            return topic
    
    def update_activity(self, topic_name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Update topic activity timestamp and metadata.
        
        Args:
            topic_name: Name of the topic
            metadata: Optional metadata to update
        """
        with self._lock:
            if topic_name in self.topics:
                self.topics[topic_name].update_activity(metadata)
            else:
                # Auto-register if not exists
                self.auto_register(topic_name, metadata)
    
    def get_core_url(self, topic_name: str) -> Optional[str]:
        """Get ORAC Core URL for a topic.
        
        Args:
            topic_name: Name of the topic
        
        Returns:
            Override URL or None (use default)
        """
        with self._lock:
            topic = self.topics.get(topic_name)
            return topic.orac_core_url if topic else None
    
    def set_core_url(self, topic_name: str, core_url: Optional[str]) -> None:
        """Set Core URL override for a topic.

        Args:
            topic_name: Name of the topic
            core_url: Core URL override (None to use default)
        """
        with self._lock:
            if topic_name not in self.topics:
                # Auto-register if not exists
                self.auto_register(topic_name)

            self.topics[topic_name].orac_core_url = core_url
            self.save()

    def set_wake_words_to_strip(self, topic_name: str, wake_words: Optional[str]) -> None:
        """Set wake words to strip for a topic.

        Args:
            topic_name: Name of the topic
            wake_words: Comma-separated wake words (e.g., "computer, hey computer")
        """
        with self._lock:
            if topic_name not in self.topics:
                # Auto-register if not exists
                self.auto_register(topic_name)

            self.topics[topic_name].wake_words_to_strip = wake_words
            self.save()
    
    def get_active_topics(self) -> List[TopicConfig]:
        """Get list of active topics (recent heartbeats).
        
        Returns:
            List of active TopicConfig instances
        """
        with self._lock:
            return [
                topic for topic in self.topics.values()
                if topic.is_active
            ]
    
    def get_all_topics(self) -> List[TopicConfig]:
        """Get all registered topics.
        
        Returns:
            List of all TopicConfig instances
        """
        with self._lock:
            return list(self.topics.values())
    
    def get_topic(self, topic_name: str) -> Optional[TopicConfig]:
        """Get a specific topic configuration.
        
        Args:
            topic_name: Name of the topic
        
        Returns:
            TopicConfig or None if not found
        """
        with self._lock:
            return self.topics.get(topic_name)
    
    def remove_topic(self, topic_name: str) -> bool:
        """Remove a topic from the registry.
        
        Args:
            topic_name: Name of the topic
        
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if topic_name in self.topics:
                del self.topics[topic_name]
                self.save()
                return True
            return False
    
    def group_by_core_url(self, topics: List[str]) -> Dict[str, List[str]]:
        """Group topics by their Core URL for batch forwarding.
        
        Args:
            topics: List of topic names
        
        Returns:
            Dict mapping Core URL to list of topic names
        """
        grouped = {}
        default_topics = []
        
        with self._lock:
            for topic_name in topics:
                core_url = self.get_core_url(topic_name)
                if core_url:
                    if core_url not in grouped:
                        grouped[core_url] = []
                    grouped[core_url].append(topic_name)
                else:
                    default_topics.append(topic_name)
        
        # Add default topics with None key
        if default_topics:
            grouped[None] = default_topics
        
        return grouped
    
    def save(self) -> None:
        """Persist topics to YAML file."""
        try:
            with self._lock:
                data = {
                    "topics": [
                        {
                            **topic.dict(),
                            "last_seen": topic.last_seen.isoformat() if topic.last_seen else None
                        } for topic in self.topics.values()
                    ]
                }
                
                with open(self.topics_file, 'w') as f:
                    yaml.safe_dump(data, f, default_flow_style=False)
                
                logger.debug(f"Saved {len(self.topics)} topics to {self.topics_file}")
        except Exception as e:
            logger.error(f"Failed to save topics: {e}")
    
    def load(self) -> None:
        """Load topics from YAML file."""
        if not self.topics_file.exists():
            logger.info("No existing topics file, starting fresh")
            return
        
        try:
            with open(self.topics_file, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            topics = data.get("topics", [])
            for topic_data in topics:
                # Convert ISO format strings back to datetime
                if topic_data.get("last_seen"):
                    last_seen = topic_data["last_seen"]
                    if isinstance(last_seen, str):
                        topic_data["last_seen"] = datetime.fromisoformat(last_seen)
                    elif not isinstance(last_seen, datetime):
                        # Handle other potential formats (e.g., from YAML datetime parsing)
                        topic_data["last_seen"] = datetime.fromisoformat(str(last_seen))
                
                topic = TopicConfig(**topic_data)
                self.topics[topic.name] = topic
            
            logger.info(f"Loaded {len(self.topics)} topics from {self.topics_file}")
        except Exception as e:
            logger.error(f"Failed to load topics: {e}")
            # Start fresh if load fails
            self.topics = {}