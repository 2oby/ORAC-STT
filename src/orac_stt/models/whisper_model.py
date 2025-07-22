"""Whisper model management and loading."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import time
import torch
import whisper

from ..config.settings import ModelConfig
from ..utils.logging import get_logger

logger = get_logger(__name__)


class WhisperModelLoader:
    """Manage Whisper model loading and caching."""
    
    # Model size mapping
    MODEL_SIZES = {
        "whisper-tiny": "tiny",
        "whisper-tiny-int8": "tiny",
        "whisper-base": "base",
        "whisper-small": "small",
        "whisper-medium": "medium",
        "whisper-large": "large",
        "whisper-large-v2": "large-v2",
        "whisper-large-v3": "large-v3",
    }
    
    def __init__(self, config: ModelConfig):
        """Initialize model loader.
        
        Args:
            config: Model configuration
        """
        self.config = config
        self._model: Optional[whisper.Whisper] = None
        self._load_time: Optional[float] = None
        
    @property
    def model(self) -> whisper.Whisper:
        """Get loaded model, loading if necessary."""
        if self._model is None:
            self.load_model()
        return self._model
    
    def load_model(self) -> None:
        """Load Whisper model with caching."""
        start_time = time.time()
        
        model_name = self.config.name
        model_size = self.MODEL_SIZES.get(model_name, "tiny")
        
        logger.info(f"Loading Whisper model: {model_name} (size: {model_size})")
        
        try:
            # Set cache directory
            os.environ['WHISPER_CACHE_DIR'] = str(self.config.cache_dir)
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Determine device
            device = self._get_device()
            
            # Load model
            self._model = whisper.load_model(
                model_size,
                device=device,
                download_root=str(self.config.cache_dir)
            )
            
            # Apply INT8 quantization if requested
            if "int8" in model_name.lower():
                self._apply_int8_quantization()
            
            self._load_time = time.time() - start_time
            
            logger.info(
                f"Model loaded successfully",
                extra={
                    "model": model_name,
                    "device": device,
                    "load_time": f"{self._load_time:.2f}s"
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _get_device(self) -> str:
        """Determine device to use for model."""
        if self.config.device == "cuda" and torch.cuda.is_available():
            logger.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
            return "cuda"
        else:
            if self.config.device == "cuda":
                logger.warning("CUDA requested but not available, falling back to CPU")
            return "cpu"
    
    def _apply_int8_quantization(self) -> None:
        """Apply INT8 quantization to model."""
        logger.info("Applying INT8 quantization")
        # Note: Full INT8 quantization requires additional libraries
        # This is a placeholder for future implementation
        # For now, we'll use the standard model
        pass
    
    def unload_model(self) -> None:
        """Unload model from memory."""
        if self._model is not None:
            del self._model
            self._model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model unloaded from memory")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded model."""
        if self._model is None:
            return {
                "loaded": False,
                "name": self.config.name
            }
        
        return {
            "loaded": True,
            "name": self.config.name,
            "device": str(next(self._model.parameters()).device),
            "load_time": self._load_time,
            "n_mels": self._model.dims.n_mels,
            "n_audio_ctx": self._model.dims.n_audio_ctx,
            "n_audio_state": self._model.dims.n_audio_state,
        }