"""Audio file validation utilities."""

import io
from typing import Tuple, Optional
import wave
import numpy as np

from ..utils.logging import get_logger

logger = get_logger(__name__)


class AudioValidationError(Exception):
    """Raised when audio validation fails."""
    pass


class AudioValidator:
    """Validate audio files according to requirements."""
    
    REQUIRED_SAMPLE_RATE = 16000
    REQUIRED_CHANNELS = 1
    REQUIRED_SAMPLE_WIDTH = 2  # 16-bit
    MAX_DURATION_SECONDS = 15
    
    @classmethod
    def validate_wav_file(cls, audio_data: bytes) -> Tuple[np.ndarray, int]:
        """Validate WAV file and return audio array.
        
        Args:
            audio_data: Raw audio file bytes
            
        Returns:
            Tuple of (audio_array, sample_rate)
            
        Raises:
            AudioValidationError: If validation fails
        """
        try:
            # Open WAV file from bytes
            with io.BytesIO(audio_data) as wav_buffer:
                with wave.open(wav_buffer, 'rb') as wav_file:
                    # Get audio parameters
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    sample_rate = wav_file.getframerate()
                    num_frames = wav_file.getnframes()
                    
                    # Validate channels
                    if channels != cls.REQUIRED_CHANNELS:
                        raise AudioValidationError(
                            f"Audio must be mono (1 channel), got {channels} channels"
                        )
                    
                    # Validate sample width
                    if sample_width != cls.REQUIRED_SAMPLE_WIDTH:
                        raise AudioValidationError(
                            f"Audio must be 16-bit, got {sample_width * 8}-bit"
                        )
                    
                    # Validate sample rate
                    if sample_rate != cls.REQUIRED_SAMPLE_RATE:
                        raise AudioValidationError(
                            f"Audio must be {cls.REQUIRED_SAMPLE_RATE}Hz, got {sample_rate}Hz"
                        )
                    
                    # Calculate duration
                    duration = num_frames / sample_rate
                    if duration > cls.MAX_DURATION_SECONDS:
                        raise AudioValidationError(
                            f"Audio duration {duration:.1f}s exceeds maximum {cls.MAX_DURATION_SECONDS}s"
                        )
                    
                    # Read audio data
                    audio_bytes = wav_file.readframes(num_frames)
                    
            # Convert to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            
            # Normalize to float32 [-1, 1]
            audio_array = audio_array.astype(np.float32) / 32768.0
            
            logger.debug(
                "Validated audio",
                extra={
                    "duration": duration,
                    "sample_rate": sample_rate,
                    "shape": audio_array.shape
                }
            )
            
            return audio_array, sample_rate
            
        except wave.Error as e:
            raise AudioValidationError(f"Invalid WAV file: {e}")
        except Exception as e:
            raise AudioValidationError(f"Audio validation failed: {e}")
    
    @classmethod
    def validate_audio_array(
        cls, 
        audio: np.ndarray, 
        sample_rate: int
    ) -> None:
        """Validate audio array.
        
        Args:
            audio: Audio array
            sample_rate: Sample rate in Hz
            
        Raises:
            AudioValidationError: If validation fails
        """
        # Check sample rate
        if sample_rate != cls.REQUIRED_SAMPLE_RATE:
            raise AudioValidationError(
                f"Audio must be {cls.REQUIRED_SAMPLE_RATE}Hz, got {sample_rate}Hz"
            )
        
        # Check duration
        duration = len(audio) / sample_rate
        if duration > cls.MAX_DURATION_SECONDS:
            raise AudioValidationError(
                f"Audio duration {duration:.1f}s exceeds maximum {cls.MAX_DURATION_SECONDS}s"
            )
        
        # Check if mono
        if audio.ndim > 1 and audio.shape[1] > 1:
            raise AudioValidationError(
                f"Audio must be mono, got {audio.shape[1]} channels"
            )