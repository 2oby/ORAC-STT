"""Command history buffer for storing recent transcriptions."""

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid

from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Command:
    """Represents a single transcribed command."""
    id: str
    text: str
    audio_path: Optional[Path]
    timestamp: datetime
    duration: float
    confidence: float
    language: Optional[str]
    processing_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'text': self.text,
            'audio_path': str(self.audio_path) if self.audio_path else None,
            'timestamp': self.timestamp.isoformat(),
            'duration': self.duration,
            'confidence': self.confidence,
            'language': self.language,
            'processing_time': self.processing_time
        }


class CommandBuffer:
    """Thread-safe circular buffer for command history."""
    
    def __init__(self, max_size: int = 5):
        """Initialize command buffer.
        
        Args:
            max_size: Maximum number of commands to store
        """
        self.max_size = max_size
        self._buffer = deque(maxlen=max_size)
        self._lock = threading.RLock()
        self._observers = []
        logger.info(f"Initialized command buffer with max size {max_size}")
    
    def add_command(
        self,
        text: str,
        audio_path: Optional[Path],
        duration: float,
        confidence: float,
        processing_time: float,
        language: Optional[str] = None
    ) -> Command:
        """Add a new command to the buffer.
        
        Args:
            text: Transcribed text
            audio_path: Path to audio file
            duration: Audio duration in seconds
            confidence: Confidence score (0-1)
            processing_time: Time taken to process
            language: Detected language code
            
        Returns:
            The created Command object
        """
        command = Command(
            id=str(uuid.uuid4()),
            text=text,
            audio_path=audio_path,
            timestamp=datetime.utcnow(),
            duration=duration,
            confidence=confidence,
            language=language,
            processing_time=processing_time
        )
        
        with self._lock:
            # If buffer is full, the oldest command will be removed automatically
            old_size = len(self._buffer)
            self._buffer.append(command)
            
            if old_size == self.max_size:
                logger.debug(f"Buffer full, removed oldest command")
        
        logger.info(f"Added command to buffer: '{text[:50]}...' (id: {command.id})")
        
        # Notify observers
        self._notify_observers(command)
        
        return command
    
    def get_commands(self, limit: Optional[int] = None) -> List[Command]:
        """Get recent commands from buffer.
        
        Args:
            limit: Maximum number of commands to return (default: all)
            
        Returns:
            List of commands, newest first
        """
        with self._lock:
            commands = list(self._buffer)
        
        # Reverse to get newest first
        commands.reverse()
        
        if limit:
            commands = commands[:limit]
            
        return commands
    
    def get_command(self, command_id: str) -> Optional[Command]:
        """Get a specific command by ID.
        
        Args:
            command_id: Command ID to retrieve
            
        Returns:
            Command object or None if not found
        """
        with self._lock:
            for command in self._buffer:
                if command.id == command_id:
                    return command
        return None
    
    def clear(self) -> None:
        """Clear all commands from buffer."""
        with self._lock:
            self._buffer.clear()
        logger.info("Cleared command buffer")
    
    def add_observer(self, callback) -> None:
        """Add an observer to be notified of new commands.
        
        Args:
            callback: Function to call with new Command object
        """
        self._observers.append(callback)
        logger.debug(f"Added observer, total: {len(self._observers)}")
    
    def remove_observer(self, callback) -> None:
        """Remove an observer.
        
        Args:
            callback: Function to remove from observers
        """
        if callback in self._observers:
            self._observers.remove(callback)
            logger.debug(f"Removed observer, remaining: {len(self._observers)}")
    
    def _notify_observers(self, command: Command) -> None:
        """Notify all observers of a new command.
        
        Args:
            command: The new command to broadcast
        """
        for observer in self._observers:
            try:
                observer(command)
            except Exception as e:
                logger.error(f"Error notifying observer: {e}")
    
    @property
    def size(self) -> int:
        """Get current number of commands in buffer."""
        with self._lock:
            return len(self._buffer)
    
    @property
    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return self.size >= self.max_size