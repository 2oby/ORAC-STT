"""Speech-to-Text API endpoints."""

import time
from typing import Dict, Any, Optional
import asyncio
from pathlib import Path
import shutil
from datetime import datetime
import soundfile as sf
from dataclasses import dataclass

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import numpy as np

from ..config.settings import Settings
from ..audio.processor import AudioProcessor
from ..audio.validator import AudioValidationError
from ..models.unified_loader import UnifiedWhisperLoader
from ..utils.logging import get_logger
from ..history.command_buffer import CommandBuffer
from ..integrations.orac_core_client import ORACCoreClient
from ..models.heartbeat import HeartbeatRequest, HeartbeatResponse
from ..core.heartbeat_manager import get_heartbeat_manager
from ..dependencies import get_model_loader, get_command_buffer, get_core_client

router = APIRouter()
logger = get_logger(__name__)

# Debug recording settings
DEBUG_RECORDINGS_DIR = Path("/app/debug_recordings")
MAX_DEBUG_RECORDINGS = 5


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


@dataclass
class TranscriptionResult:
    """Result of transcription operation."""
    text: str
    confidence: float
    language: str
    has_error: bool = False
    error_message: Optional[str] = None

    @property
    def should_forward(self) -> bool:
        """Check if result should be forwarded to Core."""
        return (
            not self.has_error
            and self.text.strip()
            and not self.text.startswith("[")
        )

    def get_metadata(self, duration: float, processing_time: float) -> dict:
        """Get metadata dictionary for Core forwarding."""
        return {
            "confidence": self.confidence,
            "language": self.language,
            "duration": duration,
            "processing_time": processing_time
        }


def init_debug_recordings():
    """Initialize debug recordings directory."""
    if not DEBUG_RECORDINGS_DIR.exists():
        DEBUG_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created debug recordings directory: {DEBUG_RECORDINGS_DIR}")


def save_debug_recording(audio_data: np.ndarray, sample_rate: int, transcription: str = "") -> Optional[Path]:
    """Save audio data as WAV file for debugging.
    
    Maintains a circular buffer of the last MAX_DEBUG_RECORDINGS files.
    
    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate
        transcription: Transcribed text (for filename)
        
    Returns:
        Path to saved file or None if save failed
    """
    init_debug_recordings()
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # ms precision
    safe_text = transcription[:30].replace(" ", "_").replace("/", "_") if transcription else "empty"
    filename = f"debug_{timestamp}_{safe_text}.wav"
    filepath = DEBUG_RECORDINGS_DIR / filename
    
    try:
        # Save the audio file
        sf.write(filepath, audio_data, sample_rate)
        logger.info(f"Saved debug recording: {filename} ({len(audio_data)/sample_rate:.2f}s)")
        
        # Clean up old recordings (keep separate from command buffer recordings)
        recordings = sorted(DEBUG_RECORDINGS_DIR.glob("debug_*.wav"))
        if len(recordings) > MAX_DEBUG_RECORDINGS:
            for old_file in recordings[:-MAX_DEBUG_RECORDINGS]:
                old_file.unlink()
                logger.debug(f"Removed old debug recording: {old_file.name}")
        
        return filepath
                
    except Exception as e:
        logger.error(f"Failed to save debug recording: {e}")
        return None


async def transcribe_audio(
    audio_data: np.ndarray,
    sample_rate: int,
    model_loader: UnifiedWhisperLoader,
    language: Optional[str] = None,
    task: str = "transcribe"
) -> Dict[str, Any]:
    """Transcribe audio data using the model.

    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate (must be 16000)
        model_loader: Model loader instance (injected)
        language: Language code
        task: Task type (transcribe or translate)

    Returns:
        Transcription results
    """
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


async def load_and_validate_audio(
    file: UploadFile
) -> tuple[np.ndarray, int, float]:
    """Load and validate audio from uploaded file.

    Args:
        file: Uploaded audio file

    Returns:
        Tuple of (audio_data, sample_rate, duration)

    Raises:
        AudioValidationError: If audio is invalid
    """
    # Read file
    audio_bytes = await file.read()

    # Load and validate
    audio_processor = AudioProcessor()
    audio_data, sample_rate = audio_processor.load_audio(audio_bytes)

    # Get duration
    duration = audio_processor.get_audio_duration(audio_data, sample_rate)

    # Prepare for model
    audio_data = audio_processor.prepare_for_whisper(audio_data)

    logger.info(
        "Audio loaded",
        extra={
            "file_name": file.filename,
            "size_bytes": len(audio_bytes),
            "duration": duration,
            "sample_rate": sample_rate
        }
    )

    return audio_data, sample_rate, duration


async def save_debug_recording_if_enabled(
    audio_data: np.ndarray,
    sample_rate: int,
    transcription: str
) -> Optional[Path]:
    """Save debug recording immediately if enabled.

    Args:
        audio_data: Audio samples
        sample_rate: Sample rate
        transcription: Transcribed text (for filename)

    Returns:
        Path to saved file or None
    """
    return save_debug_recording(audio_data, sample_rate, transcription)


async def transcribe_with_error_handling(
    audio_data: np.ndarray,
    sample_rate: int,
    model_loader: UnifiedWhisperLoader,
    language: Optional[str],
    task: str,
    start_time: float
) -> TranscriptionResult:
    """Transcribe audio with comprehensive error handling.

    Args:
        audio_data: Audio samples
        sample_rate: Sample rate
        model_loader: Model loader instance
        language: Optional language code
        task: Task type (transcribe/translate)
        start_time: Start timestamp for logging

    Returns:
        TranscriptionResult with text and metadata
    """
    try:
        result = await transcribe_audio(
            audio_data,
            sample_rate,
            model_loader,
            language=language,
            task=task
        )

        text = result.get("text", "").strip()
        confidence = result.get("confidence", 0.0)
        detected_language = result.get("language", language or "unknown")

        logger.info(
            "Transcription complete",
            extra={
                "text_length": len(text),
                "confidence": confidence,
                "language": detected_language,
                "processing_time": time.time() - start_time
            }
        )

        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language=detected_language,
            has_error=False
        )

    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        return TranscriptionResult(
            text=f"[Transcription Failed: {str(e)}]",
            confidence=0.0,
            language="unknown",
            has_error=True,
            error_message=str(e)
        )


async def add_to_command_history(
    command_buffer: CommandBuffer,
    text: str,
    audio_path: Optional[Path],
    duration: float,
    confidence: float,
    processing_time: float,
    language: str,
    has_error: bool,
    error_message: Optional[str]
) -> None:
    """Add transcription result to command history buffer.

    Args:
        command_buffer: Command buffer instance
        text: Transcribed text or error message
        audio_path: Path to saved audio file
        duration: Audio duration
        confidence: Confidence score
        processing_time: Processing time
        language: Detected language
        has_error: Whether an error occurred
        error_message: Optional error message
    """
    try:
        command_buffer.add_command(
            text=text if text else "[No transcription]",
            audio_path=audio_path,
            duration=duration,
            confidence=confidence,
            processing_time=processing_time,
            language=language,
            has_error=has_error,
            error_message=error_message
        )
        logger.info(f"Added {'error' if has_error else 'successful'} command to buffer")
    except Exception as e:
        logger.error(f"Failed to add to command buffer: {e}")


async def forward_to_core_async(
    core_client: ORACCoreClient,
    text: str,
    topic: str,
    metadata: dict
) -> None:
    """Forward transcription to ORAC Core asynchronously.

    Args:
        core_client: ORAC Core client instance
        text: Transcribed text
        topic: Topic for routing
        metadata: Additional metadata
    """
    try:
        # Forward asynchronously (don't wait for response)
        asyncio.create_task(
            core_client.forward_transcription(
                text=text,
                topic=topic,
                metadata=metadata
            )
        )

        logger.info(f"Forwarded transcription to ORAC Core with topic '{topic}'")
    except Exception as e:
        logger.error(f"Failed to forward to ORAC Core: {e}")


def build_transcription_response(
    result: TranscriptionResult,
    duration: float,
    processing_time: float
) -> TranscriptionResponse:
    """Build TranscriptionResponse from result.

    Args:
        result: Transcription result
        duration: Audio duration
        processing_time: Processing time

    Returns:
        TranscriptionResponse for API
    """
    if result.has_error:
        return TranscriptionResponse(
            text="",  # Empty text for errors
            confidence=0.0,
            language="unknown",
            duration=duration,
            processing_time=processing_time
        )
    else:
        return TranscriptionResponse(
            text=result.text,
            confidence=result.confidence,
            language=result.language,
            duration=duration,
            processing_time=processing_time
        )


def handle_validation_error(
    error: AudioValidationError,
    command_buffer: CommandBuffer,
    processing_time: float
) -> TranscriptionResponse:
    """Handle audio validation errors.

    Args:
        error: Validation error
        command_buffer: Command buffer for recording error
        processing_time: Processing time

    Returns:
        Error response
    """
    logger.warning(f"Audio validation failed: {error}")

    # Record error in command buffer
    try:
        command_buffer.add_command(
            text=f"[Invalid Audio: {str(error)}]",
            audio_path=None,
            duration=0.0,
            confidence=0.0,
            processing_time=processing_time,
            language="unknown",
            has_error=True,
            error_message=f"Invalid audio: {str(error)}"
        )
    except Exception as e:
        logger.error(f"Failed to record validation error: {e}")

    return TranscriptionResponse(
        text="",
        confidence=0.0,
        language="unknown",
        duration=0.0,
        processing_time=processing_time
    )


def handle_unexpected_error(
    error: Exception,
    command_buffer: CommandBuffer,
    processing_time: float
) -> TranscriptionResponse:
    """Handle unexpected errors.

    Args:
        error: Unexpected error
        command_buffer: Command buffer for recording error
        processing_time: Processing time

    Returns:
        Error response
    """
    logger.error(f"Processing failed: {error}", exc_info=True)

    # Record error in command buffer
    try:
        command_buffer.add_command(
            text=f"[Processing Error: {str(error)}]",
            audio_path=None,
            duration=0.0,
            confidence=0.0,
            processing_time=processing_time,
            language="unknown",
            has_error=True,
            error_message=str(error)
        )
    except Exception as e:
        logger.error(f"Failed to record unexpected error: {e}")

    return TranscriptionResponse(
        text="",
        confidence=0.0,
        language="unknown",
        duration=0.0,
        processing_time=processing_time
    )


@router.post("/stream/{topic}", response_model=TranscriptionResponse)
async def transcribe_stream_with_topic(
    topic: str,
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = None,
    task: str = "transcribe",
    forward_to_core: bool = True,
    model_loader: UnifiedWhisperLoader = Depends(get_model_loader),
    command_buffer: CommandBuffer = Depends(get_command_buffer),
    core_client: ORACCoreClient = Depends(get_core_client)
) -> TranscriptionResponse:
    """Transcribe audio from uploaded file with topic support.

    This endpoint accepts audio files, transcribes them, and optionally
    forwards the transcription to ORAC Core with the specified topic.

    Args:
        topic: Topic ID for ORAC Core routing
        file: Audio file upload
        language: Optional language code
        task: Task type (transcribe or translate)
        forward_to_core: Whether to forward transcription to ORAC Core
        model_loader: Model loader instance (injected)
        command_buffer: Command buffer instance (injected)
        core_client: ORAC Core client instance (injected)

    Returns:
        Transcription response with text and metadata
    """
    return await _transcribe_impl(
        file=file,
        language=language,
        task=task,
        topic=topic,
        forward_to_core=forward_to_core,
        model_loader=model_loader,
        command_buffer=command_buffer,
        core_client=core_client
    )


@router.post("/stream", response_model=TranscriptionResponse)
async def transcribe_stream(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    language: Optional[str] = None,
    task: str = "transcribe",
    forward_to_core: bool = True,
    model_loader: UnifiedWhisperLoader = Depends(get_model_loader),
    command_buffer: CommandBuffer = Depends(get_command_buffer),
    core_client: ORACCoreClient = Depends(get_core_client)
) -> TranscriptionResponse:
    """Transcribe audio from uploaded file (backward compatibility).

    Defaults to 'general' topic for backward compatibility.
    """
    return await _transcribe_impl(
        file=file,
        language=language,
        task=task,
        topic="general",
        forward_to_core=forward_to_core,
        model_loader=model_loader,
        command_buffer=command_buffer,
        core_client=core_client
    )


async def _transcribe_impl(
    file: UploadFile,
    model_loader: UnifiedWhisperLoader,
    command_buffer: CommandBuffer,
    core_client: ORACCoreClient,
    language: Optional[str] = None,
    task: str = "transcribe",
    topic: str = "general",
    forward_to_core: bool = True
) -> TranscriptionResponse:
    """Main transcription orchestrator.

    Orchestrates the transcription workflow by delegating to specialized helper
    functions. Each step is independently testable and has a single responsibility.

    Args:
        file: Uploaded audio file
        model_loader: Model loader instance
        command_buffer: Command history buffer
        core_client: ORAC Core client
        language: Optional language code
        task: Task type (transcribe/translate)
        topic: Topic for routing
        forward_to_core: Whether to forward to Core

    Returns:
        TranscriptionResponse with results or error info
    """
    start_time = time.time()

    try:
        # 1. Load and validate audio
        audio_data, sample_rate, duration = await load_and_validate_audio(file)

        # 2. Save debug recording immediately
        audio_path = await save_debug_recording_if_enabled(
            audio_data, sample_rate, "[Processing...]"
        )

        # 3. Transcribe with error handling
        result = await transcribe_with_error_handling(
            audio_data, sample_rate, model_loader, language, task, start_time
        )

        # 4. Add to command history
        await add_to_command_history(
            command_buffer=command_buffer,
            text=result.text,
            audio_path=audio_path,
            duration=duration,
            confidence=result.confidence,
            processing_time=time.time() - start_time,
            language=result.language,
            has_error=result.has_error,
            error_message=result.error_message
        )

        # 5. Forward to ORAC Core if successful
        if result.should_forward and forward_to_core:
            await forward_to_core_async(
                core_client=core_client,
                text=result.text,
                topic=topic,
                metadata=result.get_metadata(duration, time.time() - start_time)
            )

        # 6. Build and return response
        return build_transcription_response(result, duration, time.time() - start_time)

    except AudioValidationError as e:
        return handle_validation_error(e, command_buffer, time.time() - start_time)
    except Exception as e:
        return handle_unexpected_error(e, command_buffer, time.time() - start_time)


@router.get("/health")
async def stt_health(
    model_loader: UnifiedWhisperLoader = Depends(get_model_loader)
) -> Dict[str, Any]:
    """Check STT endpoint health and model status."""
    try:
        
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
async def preload_model(
    model_loader: UnifiedWhisperLoader = Depends(get_model_loader)
) -> Dict[str, str]:
    """Preload the model for faster first inference.

    This endpoint can be called during startup to ensure the model
    is loaded and ready before the first transcription request.
    """
    try:
        start_time = time.time()
        
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


@router.get("/debug/recordings")
async def list_debug_recordings() -> Dict[str, Any]:
    """List available debug recordings."""
    init_debug_recordings()
    
    recordings = []
    for file in sorted(DEBUG_RECORDINGS_DIR.glob("debug_*.wav"), reverse=True):
        stat = file.stat()
        recordings.append({
            "filename": file.name,
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "duration_estimate": stat.st_size / (16000 * 2)  # Rough estimate
        })
    
    return {
        "count": len(recordings),
        "max_recordings": MAX_DEBUG_RECORDINGS,
        "recordings": recordings
    }


@router.get("/debug/recordings/{filename}")
async def get_debug_recording(filename: str):
    """Retrieve a specific debug recording."""
    filepath = DEBUG_RECORDINGS_DIR / filename
    
    if not filepath.exists() or not filepath.name.startswith("debug_"):
        raise HTTPException(status_code=404, detail="Recording not found")
    
    return StreamingResponse(
        open(filepath, "rb"),
        media_type="audio/wav",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def receive_heartbeat(request: HeartbeatRequest) -> HeartbeatResponse:
    """Receive batched heartbeat from Hey ORAC instances.
    
    This endpoint accepts heartbeats containing multiple wake word models
    from a single Hey ORAC instance. Active models are forwarded to ORAC Core
    for automatic topic creation and health tracking.
    
    Args:
        request: Batched heartbeat with all models from an instance
        
    Returns:
        Response indicating processing status
    """
    heartbeat_manager = get_heartbeat_manager()
    return await heartbeat_manager.process_heartbeat(request)


@router.get("/heartbeat/status")
async def get_heartbeat_status() -> Dict[str, Any]:
    """Get current heartbeat tracking status.
    
    Returns information about active Hey ORAC instances and their topics.
    """
    heartbeat_manager = get_heartbeat_manager()
    return heartbeat_manager.get_status()