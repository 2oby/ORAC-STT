"""Unified model loader supporting whisper.cpp, whisper-server, and PyTorch backends."""

import os
import time
from pathlib import Path
from typing import Dict, Optional, Any, Union
import numpy as np

from ..config.settings import ModelConfig
from ..utils.logging import get_logger

# Determine which backend to use
# Priority: whisper-server > whisper.cpp > PyTorch
USE_WHISPER_SERVER = os.environ.get("USE_WHISPER_SERVER", "false").lower() == "true"
USE_WHISPER_CPP = os.environ.get("USE_WHISPER_CPP", "true").lower() == "true"
WHISPER_SERVER_URL = os.environ.get("WHISPER_SERVER_URL", "http://localhost:8080")

if USE_WHISPER_SERVER:
    from .whisper_server import WhisperServerModel
elif USE_WHISPER_CPP:
    from .whisper_cpp import WhisperCppModel
else:
    import torch
    import whisper

logger = get_logger(__name__)


class UnifiedWhisperLoader:
    """Unified loader for Whisper models supporting multiple backends."""
    
    # Model size mapping for whisper.cpp
    WHISPER_CPP_MODELS = {
        "whisper-tiny": "ggml-tiny.bin",
        "whisper-base": "ggml-base.bin", 
        "whisper-small": "ggml-small.bin",
        "whisper-medium": "ggml-medium.bin",
        "whisper-large": "ggml-large-v3.bin",
        "whisper-large-v3": "ggml-large-v3.bin",
    }
    
    # Model size mapping for PyTorch
    PYTORCH_MODELS = {
        "whisper-tiny": "tiny",
        "whisper-base": "base",
        "whisper-small": "small",
        "whisper-medium": "medium", 
        "whisper-large": "large",
        "whisper-large-v3": "large-v3",
    }
    
    def __init__(self, config: ModelConfig):
        """Initialize unified loader.

        Args:
            config: Model configuration
        """
        self.config = config
        self.use_whisper_server = USE_WHISPER_SERVER
        self.use_whisper_cpp = USE_WHISPER_CPP
        self.whisper_server_url = WHISPER_SERVER_URL
        self._model: Optional[Any] = None
        self._load_time: Optional[float] = None

        # Determine backend name for logging
        if self.use_whisper_server:
            backend = f"whisper-server ({self.whisper_server_url})"
        elif self.use_whisper_cpp:
            backend = "whisper.cpp"
        else:
            backend = "PyTorch"

        logger.info(f"Initializing UnifiedWhisperLoader with backend: {backend}")
    
    @property
    def model(self) -> Any:
        """Get loaded model, loading if necessary."""
        if self._model is None:
            self.load_model()
        return self._model
    
    def load_model(self) -> None:
        """Load model using appropriate backend."""
        start_time = time.time()
        model_name = self.config.name

        try:
            if self.use_whisper_server:
                self._load_whisper_server()
            elif self.use_whisper_cpp:
                self._load_whisper_cpp(model_name)
            else:
                self._load_pytorch(model_name)

            self._load_time = time.time() - start_time
            logger.info(f"Model loaded successfully in {self._load_time:.2f}s")

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def _load_whisper_server(self) -> None:
        """Initialize whisper-server client."""
        logger.info(f"Connecting to whisper-server at {self.whisper_server_url}")

        self._model = WhisperServerModel(
            server_url=self.whisper_server_url,
            timeout=30.0,
            language="en",
        )

        # Wait for server to be ready (model may still be loading)
        if not self._model.wait_for_ready(timeout=60.0):
            raise RuntimeError(
                f"Whisper-server at {self.whisper_server_url} not ready"
            )
    
    def _load_whisper_cpp(self, model_name: str) -> None:
        """Load whisper.cpp model."""
        # Get GGML model filename
        ggml_name = self.WHISPER_CPP_MODELS.get(model_name, "ggml-base.bin")
        model_path = Path(self.config.cache_dir) / ggml_name
        
        # Whisper binary path - whisper.cpp builds as "whisper-cli"
        whisper_bin = Path("/app/third_party/whisper_cpp/bin/whisper-cli")
        
        # Check if binary exists, if not try alternate location
        if not whisper_bin.exists():
            whisper_bin = Path(self.config.cache_dir).parent / "whisper_cpp" / "bin" / "whisper-cli"
        
        logger.info(f"Loading whisper.cpp model: {model_path}")
        logger.info(f"Using whisper binary: {whisper_bin}")
        
        self._model = WhisperCppModel(
            model_path=str(model_path),
            whisper_bin=str(whisper_bin),
            device="cuda" if self.config.device != "cpu" else "cpu"
        )
    
    def _load_pytorch(self, model_name: str) -> None:
        """Load PyTorch Whisper model."""
        model_size = self.PYTORCH_MODELS.get(model_name, "base")
        
        # Set cache directory
        os.environ['WHISPER_CACHE_DIR'] = str(self.config.cache_dir)
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine device
        device = self._get_pytorch_device()
        
        logger.info(f"Loading PyTorch Whisper model: {model_size} on {device}")
        
        self._model = whisper.load_model(
            model_size,
            device=device,
            download_root=str(self.config.cache_dir)
        )
    
    def _get_pytorch_device(self) -> str:
        """Get PyTorch device based on configuration and availability."""
        if self.config.device == "cpu":
            return "cpu"
            
        if torch.cuda.is_available():
            logger.info("CUDA available, using GPU")
            return "cuda"
        else:
            logger.warning("CUDA not available, falling back to CPU")
            return "cpu"
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Transcribe audio using loaded model.
        
        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate 
            language: Language code
            **kwargs: Additional arguments
            
        Returns:
            Transcription results
        """
        if self._model is None:
            self.load_model()
            
        # Extract task from kwargs if present
        task = kwargs.pop("task", "transcribe") if isinstance(kwargs, dict) else "transcribe"
        
        return self._model.transcribe(
            audio_data,
            sample_rate=sample_rate,
            language=language,
            **kwargs if isinstance(kwargs, dict) else {}
        )
    
    def detect_language(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000
    ) -> tuple[str, float]:
        """Detect language of audio.
        
        Args:
            audio_data: Audio samples
            sample_rate: Sample rate
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if self._model is None:
            self.load_model()
            
        if hasattr(self._model, 'detect_language'):
            return self._model.detect_language(audio_data, sample_rate)
        else:
            # Fallback for PyTorch backend
            result = self._model.transcribe(
                audio_data,
                task="detect_language"
            )
            return result.get("language", "en"), 0.9
    
    @property
    def is_multilingual(self) -> bool:
        """Check if model supports multiple languages."""
        if self._model is None:
            # Check based on model name
            return "tiny.en" not in self.config.name and "base.en" not in self.config.name
        
        if hasattr(self._model, 'is_multilingual'):
            return self._model.is_multilingual
        else:
            # PyTorch models
            return self._model.is_multilingual if hasattr(self._model, 'is_multilingual') else True
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self._model = None
        logger.info("Model resources cleaned up")