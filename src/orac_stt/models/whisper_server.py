"""Whisper-server HTTP client for persistent model inference.

This module provides a client that communicates with whisper-server via HTTP,
eliminating subprocess overhead and keeping the model loaded in memory.
"""

import io
import time
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import requests

from ..utils.logging import get_logger

logger = get_logger(__name__)


class WhisperServerModel:
    """HTTP client for whisper-server inference."""

    def __init__(
        self,
        server_url: str = "http://localhost:8080",
        timeout: float = 30.0,
        language: str = "en",
    ):
        """Initialize whisper-server client.

        Args:
            server_url: Base URL of whisper-server (e.g., http://localhost:8080)
            timeout: Request timeout in seconds
            language: Default language for transcription
        """
        self.server_url = server_url.rstrip("/")
        self.inference_url = f"{self.server_url}/inference"
        self.timeout = timeout
        self.default_language = language
        self._session = requests.Session()

        logger.info(f"WhisperServerModel initialized: {self.inference_url}")

    def _audio_to_wav_bytes(
        self, audio_data: np.ndarray, sample_rate: int
    ) -> bytes:
        """Convert numpy audio array to WAV bytes.

        Args:
            audio_data: Audio samples as numpy array (float32, -1.0 to 1.0)
            sample_rate: Sample rate in Hz

        Returns:
            WAV file as bytes
        """
        # Create in-memory WAV file
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            # Clip and convert to int16
            audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(
                np.int16
            )
            wav.writeframes(audio_int16.tobytes())

        wav_buffer.seek(0)
        return wav_buffer.read()

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Transcribe audio using whisper-server.

        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate (must be 16000 for Whisper)
            language: Language code (e.g., 'en', 'es')
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            Dictionary with transcription results:
                - text: Transcribed text
                - confidence: Confidence score (estimated)
        """
        if sample_rate != 16000:
            raise ValueError(f"Sample rate must be 16000, got {sample_rate}")

        # Convert audio to WAV bytes
        wav_bytes = self._audio_to_wav_bytes(audio_data, sample_rate)

        # Prepare form data
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data = {"response_format": "json"}

        # Add language if specified
        if language:
            data["language"] = language
        elif self.default_language:
            data["language"] = self.default_language

        start_time = time.time()

        try:
            response = self._session.post(
                self.inference_url,
                files=files,
                data=data,
                timeout=self.timeout,
            )
            response.raise_for_status()

            elapsed = time.time() - start_time
            result = response.json()

            # Extract text from response
            text = result.get("text", "").strip()

            logger.info(
                f"Transcription complete in {elapsed:.3f}s: {text[:50]}..."
            )

            return {
                "text": text,
                "confidence": 0.95 if text else 0.0,
                "inference_time": elapsed,
            }

        except requests.exceptions.Timeout:
            logger.error(f"Whisper-server request timed out after {self.timeout}s")
            raise RuntimeError("Transcription timed out")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Failed to connect to whisper-server: {e}")
            raise RuntimeError(
                f"Cannot connect to whisper-server at {self.server_url}"
            )

        except requests.exceptions.HTTPError as e:
            logger.error(f"Whisper-server HTTP error: {e}")
            raise RuntimeError(f"Transcription failed: {e}")

    def detect_language(
        self, audio_data: np.ndarray, sample_rate: int = 16000
    ) -> Tuple[str, float]:
        """Detect language of audio.

        Args:
            audio_data: Audio samples
            sample_rate: Sample rate

        Returns:
            Tuple of (language_code, confidence)
        """
        # Run transcription with auto-detect
        result = self.transcribe(audio_data, sample_rate, language="auto")

        # whisper-server may include language in response
        lang = result.get("language", "en")
        confidence = 0.9

        return lang, confidence

    @property
    def is_multilingual(self) -> bool:
        """Check if model supports multiple languages.

        Note: This depends on which model whisper-server was started with.
        We assume multilingual support by default.
        """
        return True

    def health_check(self) -> bool:
        """Check if whisper-server is running and healthy.

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            # whisper-server serves HTML at root when healthy
            response = self._session.get(
                self.server_url, timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Whisper-server health check failed: {e}")
            return False

    def wait_for_ready(self, timeout: float = 60.0, interval: float = 1.0) -> bool:
        """Wait for whisper-server to become ready.

        Args:
            timeout: Maximum time to wait in seconds
            interval: Time between health checks

        Returns:
            True if server became ready, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.health_check():
                logger.info("Whisper-server is ready")
                return True
            time.sleep(interval)

        logger.error(f"Whisper-server not ready after {timeout}s")
        return False
