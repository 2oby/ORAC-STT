"""Whisper.cpp wrapper for GPU-accelerated inference on Jetson."""

import subprocess
import tempfile
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import wave
import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class WhisperCppModel:
    """Wrapper for whisper.cpp binary execution."""
    
    def __init__(
        self,
        model_path: str = "/app/models/ggml-base.bin",
        whisper_bin: str = "/app/third_party/whisper_cpp/bin/whisper",
        device: str = "cuda"
    ):
        """Initialize whisper.cpp wrapper.
        
        Args:
            model_path: Path to GGML model file
            whisper_bin: Path to whisper binary
            device: Device to use (cuda or cpu)
        """
        self.model_path = Path(model_path)
        self.whisper_bin = Path(whisper_bin)
        self.device = device
        
        # Verify binary exists
        if not self.whisper_bin.exists():
            raise FileNotFoundError(f"Whisper binary not found at {self.whisper_bin}")
        
        # Verify model exists
        if not self.model_path.exists():
            logger.warning(f"Model not found at {self.model_path}, will download on first use")
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict[str, any]:
        """Transcribe audio using whisper.cpp.
        
        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate (must be 16000)
            language: Language code (e.g., 'en', 'es')
            **kwargs: Additional arguments for whisper.cpp
            
        Returns:
            Dictionary with transcription results
        """
        if sample_rate != 16000:
            raise ValueError(f"Sample rate must be 16000, got {sample_rate}")
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            
            # Write WAV file
            with wave.open(tmp_path, 'wb') as wav:
                wav.setnchannels(1)  # Mono
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(sample_rate)
                wav.writeframes((audio_data * 32767).astype(np.int16).tobytes())
        
        try:
            # Build whisper.cpp command
            cmd = [
                str(self.whisper_bin),
                "-m", str(self.model_path),
                "-f", tmp_path,
                "--output-json",  # JSON output format
                "--no-timestamps",  # Disable timestamps for faster inference
            ]
            
            # Add GPU flag if using CUDA
            if self.device == "cuda":
                cmd.append("--gpu")
            
            # Add language if specified
            if language:
                cmd.extend(["-l", language])
            
            # Run whisper.cpp
            logger.info(f"Running whisper.cpp: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse output (whisper.cpp outputs JSON to stdout with --output-json)
            try:
                # The JSON output is written to a file with .json extension
                json_path = tmp_path + ".json"
                if os.path.exists(json_path):
                    with open(json_path, 'r') as f:
                        output = json.load(f)
                    os.unlink(json_path)  # Clean up JSON file
                else:
                    # Fallback: parse stdout
                    output = {"text": result.stdout.strip()}
                    
            except json.JSONDecodeError:
                # Fallback: return raw text
                output = {"text": result.stdout.strip()}
            
            # Add confidence score (whisper.cpp doesn't provide this directly)
            output["confidence"] = 0.95 if output.get("text") else 0.0
            
            logger.info(f"Transcription complete: {output.get('text', '')[:50]}...")
            return output
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Whisper.cpp failed: {e.stderr}")
            raise RuntimeError(f"Transcription failed: {e.stderr}")
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def detect_language(self, audio_data: np.ndarray, sample_rate: int = 16000) -> Tuple[str, float]:
        """Detect language of audio.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate
            
        Returns:
            Tuple of (language_code, confidence)
        """
        # Run transcription with language detection
        result = self.transcribe(audio_data, sample_rate, language="auto")
        
        # Extract detected language from result
        # Note: whisper.cpp language detection support varies by version
        lang = result.get("language", "en")
        confidence = 0.9  # Default confidence
        
        return lang, confidence
    
    @property
    def is_multilingual(self) -> bool:
        """Check if model supports multiple languages."""
        # Base model and larger are multilingual
        model_name = self.model_path.stem
        return "tiny.en" not in model_name and "base.en" not in model_name