"""Audio format support hooks."""

from typing import Tuple, Protocol
import numpy as np

from ..utils.logging import get_logger

logger = get_logger(__name__)


class AudioFormatHandler(Protocol):
    """Protocol for audio format handlers."""
    
    def can_handle(self, audio_data: bytes) -> bool:
        """Check if this handler can process the audio data."""
        ...
    
    def load(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Load audio data and return array and sample rate."""
        ...


class FLACHandler:
    """FLAC format handler (stub for future implementation)."""
    
    def can_handle(self, audio_data: bytes) -> bool:
        """Check if data is FLAC format."""
        # FLAC files start with "fLaC"
        return audio_data[:4] == b'fLaC'
    
    def load(self, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Load FLAC data (not implemented)."""
        raise NotImplementedError(
            "FLAC support is planned for future release. "
            "Please use WAV format for now."
        )


class FormatRegistry:
    """Registry for audio format handlers."""
    
    def __init__(self):
        self.handlers = {
            'flac': FLACHandler(),
        }
    
    def get_handler(self, audio_data: bytes) -> AudioFormatHandler:
        """Get appropriate handler for audio data."""
        for name, handler in self.handlers.items():
            if handler.can_handle(audio_data):
                logger.info(f"Detected {name.upper()} format")
                return handler
        return None


# Global format registry
format_registry = FormatRegistry()