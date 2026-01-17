"""Audio processing utilities."""

import io
from typing import Tuple, Optional, Union
import numpy as np
import soundfile as sf
import librosa

from .validator import AudioValidator, AudioValidationError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AudioProcessor:
    """Process audio files for STT."""
    
    @staticmethod
    def load_audio(
        audio_data: Union[bytes, io.BytesIO],
        validate: bool = True
    ) -> Tuple[np.ndarray, int]:
        """Load audio from bytes or buffer.
        
        Args:
            audio_data: Audio data as bytes or BytesIO
            validate: Whether to validate audio format
            
        Returns:
            Tuple of (audio_array, sample_rate)
            
        Raises:
            AudioValidationError: If validation fails
        """
        if isinstance(audio_data, bytes):
            audio_buffer = io.BytesIO(audio_data)
        else:
            audio_buffer = audio_data
            audio_buffer.seek(0)
        
        try:
            # Try to read with soundfile (supports multiple formats)
            audio, sample_rate = sf.read(audio_buffer, dtype='float32')
            
            # Ensure mono
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)
            
            # Resample if needed
            if sample_rate != AudioValidator.REQUIRED_SAMPLE_RATE:
                logger.info(
                    f"Resampling audio from {sample_rate}Hz to "
                    f"{AudioValidator.REQUIRED_SAMPLE_RATE}Hz"
                )
                audio = librosa.resample(
                    audio,
                    orig_sr=sample_rate,
                    target_sr=AudioValidator.REQUIRED_SAMPLE_RATE
                )
                sample_rate = AudioValidator.REQUIRED_SAMPLE_RATE
            
            if validate:
                AudioValidator.validate_audio_array(audio, sample_rate)
            
            return audio, sample_rate
            
        except Exception as e:
            # Fall back to WAV validation if soundfile fails
            if isinstance(audio_data, io.BytesIO):
                audio_data = audio_data.read()
                audio_buffer.seek(0)
            
            if validate:
                return AudioValidator.validate_wav_file(audio_data)
            else:
                raise AudioValidationError(f"Failed to load audio: {e}")
    
    @staticmethod
    def prepare_for_whisper(audio: np.ndarray) -> np.ndarray:
        """Prepare audio array for Whisper model.
        
        Args:
            audio: Audio array
            
        Returns:
            Prepared audio array
        """
        # Whisper expects float32 audio normalized to [-1, 1]
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Ensure proper normalization
        if np.abs(audio).max() > 1.0:
            audio = audio / np.abs(audio).max()
        
        return audio
    
    @staticmethod
    def get_audio_duration(audio: np.ndarray, sample_rate: int) -> float:
        """Get audio duration in seconds.
        
        Args:
            audio: Audio array
            sample_rate: Sample rate in Hz
            
        Returns:
            Duration in seconds
        """
        return len(audio) / sample_rate


class AudioBuffer:
    """Manage audio buffers for streaming."""

    def __init__(self, sample_rate: int = 16000):
        """Initialize audio buffer.

        Args:
            sample_rate: Sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.buffer = np.array([], dtype=np.float32)

    def append(self, audio: np.ndarray) -> None:
        """Append audio to buffer.

        Args:
            audio: Audio array to append
        """
        self.buffer = np.concatenate([self.buffer, audio])

    def get_duration(self) -> float:
        """Get current buffer duration in seconds."""
        return len(self.buffer) / self.sample_rate

    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer = np.array([], dtype=np.float32)

    def get_audio(self) -> np.ndarray:
        """Get the current audio buffer."""
        return self.buffer.copy()


class AudioStreamBuffer:
    """Accumulates audio chunks for streaming transcription.

    Receives raw int16 audio chunks from WebSocket and buffers them
    until enough audio has accumulated for transcription.
    """

    def __init__(self, sample_rate: int = 16000, threshold_ms: int = 500):
        """Initialize streaming audio buffer.

        Args:
            sample_rate: Sample rate in Hz (default 16000 for Whisper)
            threshold_ms: Minimum audio duration in ms before transcription
        """
        self.sample_rate = sample_rate
        self.threshold_ms = threshold_ms
        self.threshold_samples = int(sample_rate * threshold_ms / 1000)
        self.buffer = np.array([], dtype=np.float32)
        self._total_samples_received = 0

    def append_int16(self, chunk: bytes) -> None:
        """Add raw int16 audio chunk to buffer.

        Args:
            chunk: Raw audio bytes (int16 format, mono, 16kHz)
        """
        # Convert int16 bytes to float32 normalized to [-1, 1]
        audio = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        self.buffer = np.concatenate([self.buffer, audio])
        self._total_samples_received += len(audio)

    def append_float32(self, chunk: bytes) -> None:
        """Add raw float32 audio chunk to buffer.

        Args:
            chunk: Raw audio bytes (float32 format, mono, 16kHz)
        """
        audio = np.frombuffer(chunk, dtype=np.float32)
        self.buffer = np.concatenate([self.buffer, audio])
        self._total_samples_received += len(audio)

    def ready_for_transcription(self) -> bool:
        """Check if enough audio has accumulated for transcription.

        Returns:
            True if buffer duration >= threshold_ms
        """
        return len(self.buffer) >= self.threshold_samples

    def get_duration_ms(self) -> float:
        """Get current buffer duration in milliseconds."""
        return (len(self.buffer) / self.sample_rate) * 1000

    def get_total_duration_ms(self) -> float:
        """Get total audio received in milliseconds."""
        return (self._total_samples_received / self.sample_rate) * 1000

    def get_audio(self) -> np.ndarray:
        """Get accumulated audio for transcription.

        Returns:
            Audio as float32 numpy array normalized to [-1, 1]
        """
        return self.buffer.copy()

    def get_audio_prepared(self) -> np.ndarray:
        """Get audio prepared for Whisper (float32, normalized).

        Returns:
            Audio ready for Whisper transcription
        """
        audio = self.buffer.copy()
        # Ensure proper normalization for Whisper
        if len(audio) > 0 and np.abs(audio).max() > 1.0:
            audio = audio / np.abs(audio).max()
        return audio

    def clear(self) -> None:
        """Clear buffer after transcription."""
        self.buffer = np.array([], dtype=np.float32)

    def reset(self) -> None:
        """Full reset including total samples counter."""
        self.buffer = np.array([], dtype=np.float32)
        self._total_samples_received = 0