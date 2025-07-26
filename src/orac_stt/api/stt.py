"""Speech-to-Text API endpoints."""

import time
from typing import Dict, Any, Optional
import asyncio
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import numpy as np

from ..config.settings import Settings
from ..config.loader import load_config
from ..audio.processor import AudioProcessor
from ..audio.validator import AudioValidationError
from ..models.unified_loader import UnifiedWhisperLoader
from ..utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Global model loader instance
_model_loader: Optional[UnifiedWhisperLoader] = None


class TranscriptionResponse(BaseModel):
    """STT transcription response model."""
    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(..., description="Confidence score (0-1)")
    language: Optional[str] = Field(None, description="Detected language code")
    duration: float = Field(..., description="Audio duration in seconds")
    processing_time: float = Field(..., description="Processing time in seconds")


class TranscriptionRequest(BaseModel):
    """STT transcription request options."""
    language: Optional[str] = Field(None, description="Language code (e.g., 'en', 'es')")
    task: str = Field("transcribe", description="Task type: transcribe or translate")


def get_model_loader() -> UnifiedWhisperLoader:
    """Get or create model loader instance."""
    global _model_loader
    
    if _model_loader is None:
        settings = load_config()
        _model_loader = UnifiedWhisperLoader(settings.model)
        logger.info("Initialized model loader")
    
    return _model_loader


async def transcribe_audio(
    audio_data: np.ndarray,
    sample_rate: int,
    language: Optional[str] = None,
    task: str = "transcribe"
) -> Dict[str, Any]:
    """Transcribe audio data using the model.
    
    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate (must be 16000)
        language: Language code
        task: Task type (transcribe or translate)
        
    Returns:
        Transcription results
    """
    model_loader = get_model_loader()
    
    # Run transcription in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    
    def transcribe_sync():
        return model_loader.transcribe(
            audio_data,
            sample_rate=sample_rate,
            language=language,
            task=task
        )
    
    result = await loop.run_in_executor(None, transcribe_sync)
    
    return result


@router.post("/stream", response_model=TranscriptionResponse)
async def transcribe_stream(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = None,
    task: str = "transcribe"
) -> TranscriptionResponse:
    """Transcribe audio from uploaded file.
    
    This endpoint accepts audio files and returns transcribed text.
    Supported formats: WAV (16kHz, 16-bit, mono)
    Maximum duration: 15 seconds
    
    Args:
        file: Audio file upload
        language: Optional language code
        task: Task type (transcribe or translate)
        
    Returns:
        Transcription response with text and metadata
    """
    start_time = time.time()
    
    try:
        # Read uploaded file
        audio_bytes = await file.read()
        
        # Load and validate audio
        audio_processor = AudioProcessor()
        audio_data, sample_rate = audio_processor.load_audio(audio_bytes)
        
        # Get audio duration
        duration = audio_processor.get_audio_duration(audio_data, sample_rate)
        
        # Prepare audio for model
        audio_data = audio_processor.prepare_for_whisper(audio_data)
        
        logger.info(
            "Processing audio",
            extra={
                "file_name": file.filename,
                "size_bytes": len(audio_bytes),
                "duration": duration,
                "sample_rate": sample_rate
            }
        )
        
        # Transcribe audio
        result = await transcribe_audio(
            audio_data,
            sample_rate,
            language=language,
            task=task
        )
        
        # Extract results
        text = result.get("text", "").strip()
        confidence = result.get("confidence", 0.0)
        detected_language = result.get("language", language)
        
        processing_time = time.time() - start_time
        
        logger.info(
            "Transcription complete",
            extra={
                "text_length": len(text),
                "confidence": confidence,
                "language": detected_language,
                "processing_time": processing_time
            }
        )
        
        return TranscriptionResponse(
            text=text,
            confidence=confidence,
            language=detected_language,
            duration=duration,
            processing_time=processing_time
        )
        
    except AudioValidationError as e:
        logger.warning(f"Audio validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Transcription failed")


@router.get("/health")
async def stt_health() -> Dict[str, Any]:
    """Check STT endpoint health and model status."""
    try:
        model_loader = get_model_loader()
        
        # Check if model is loaded
        model_loaded = model_loader._model is not None
        
        return {
            "status": "healthy" if model_loaded else "initializing",
            "model_loaded": model_loaded,
            "model_name": model_loader.config.name,
            "backend": "whisper.cpp" if model_loader.use_whisper_cpp else "pytorch",
            "device": model_loader.config.device
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.post("/preload")
async def preload_model() -> Dict[str, str]:
    """Preload the model for faster first inference.
    
    This endpoint can be called during startup to ensure the model
    is loaded and ready before the first transcription request.
    """
    try:
        start_time = time.time()
        model_loader = get_model_loader()
        
        # Load model if not already loaded
        if model_loader._model is None:
            await asyncio.get_event_loop().run_in_executor(
                None,
                model_loader.load_model
            )
        
        load_time = time.time() - start_time
        
        return {
            "status": "success",
            "message": f"Model loaded in {load_time:.2f}s"
        }
    except Exception as e:
        logger.error(f"Model preload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e}")