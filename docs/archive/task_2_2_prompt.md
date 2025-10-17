# Phase 2 - Task 2.2: Refactor Monolithic STT Function

## Context
The `_transcribe_impl()` function in `src/orac_stt/api/stt.py` is currently 157 lines long (lines 199-356) and handles 8 different responsibilities. This makes it hard to test, maintain, and understand. We need to break it down into smaller, focused, testable functions.

## Current Issues
1. **Single function does too much** - 8 different responsibilities mixed together
2. **Hard to test** - Cannot test individual steps in isolation
3. **Complex error handling** - Multiple try-except blocks intertwined with business logic
4. **Multiple levels of nesting** - Difficult to follow the flow
5. **No separation of concerns** - HTTP handling, business logic, and error handling all mixed

## Current Structure (157 lines)
The `_transcribe_impl()` function currently does:
1. Read and validate uploaded audio file
2. Load and process audio with AudioProcessor
3. Save debug recording (even if transcription fails)
4. Call transcription with error handling
5. Add result to command buffer (success or failure)
6. Forward successful transcriptions to ORAC Core
7. Handle AudioValidationError exceptions
8. Handle generic exceptions
9. Build and return response

## Goal
Break down `_transcribe_impl()` into smaller, testable functions while maintaining the exact same behavior and error handling. The main function should become an orchestrator that calls well-defined helper functions.

## New Structure (Target)

### Main Orchestrator Function
```python
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
    """Main transcription orchestrator (target: < 50 lines)."""
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
```

### Helper Functions to Create

#### 1. load_and_validate_audio()
```python
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
```

#### 2. TranscriptionResult Dataclass
```python
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
```

#### 3. transcribe_with_error_handling()
```python
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
```

#### 4. add_to_command_history()
```python
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
```

#### 5. forward_to_core_async()
```python
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
```

#### 6. build_transcription_response()
```python
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
```

#### 7. Error Handlers
```python
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
```

## Implementation Steps

1. **Create TranscriptionResult dataclass** above the functions
2. **Extract load_and_validate_audio()** - Lines 214-237
3. **Extract transcribe_with_error_handling()** - Lines 240-272
4. **Extract add_to_command_history()** - Lines 297-313
5. **Extract forward_to_core_async()** - Lines 316-338
6. **Extract build_transcription_response()** - Lines 341-356
7. **Create error handlers** for validation and unexpected errors
8. **Refactor _transcribe_impl()** to use the new functions
9. **Test each function** independently

## Testing Strategy

### Unit Tests to Add
```python
# tests/unit/test_stt_handlers.py

def test_load_and_validate_audio():
    """Test audio loading and validation."""
    # Test with valid audio
    # Test with invalid audio
    # Test with wrong format
    pass

def test_transcription_result_should_forward():
    """Test TranscriptionResult.should_forward property."""
    # Success case
    result = TranscriptionResult(text="hello", confidence=0.95, language="en")
    assert result.should_forward is True

    # Error case
    result = TranscriptionResult(text="", confidence=0.0, language="unknown", has_error=True)
    assert result.should_forward is False

    # Empty text
    result = TranscriptionResult(text="   ", confidence=0.95, language="en")
    assert result.should_forward is False

    # Error message text
    result = TranscriptionResult(text="[Error occurred]", confidence=0.0, language="en")
    assert result.should_forward is False

async def test_add_to_command_history():
    """Test adding command to buffer."""
    buffer = CommandBuffer(max_size=5)

    await add_to_command_history(
        command_buffer=buffer,
        text="test",
        audio_path=None,
        duration=1.0,
        confidence=0.95,
        processing_time=0.5,
        language="en",
        has_error=False,
        error_message=None
    )

    commands = buffer.get_commands()
    assert len(commands) == 1
    assert commands[0].text == "test"
```

### Integration Tests
Existing integration tests should continue to pass without modification since the API behavior is unchanged.

## Acceptance Criteria

- [ ] `_transcribe_impl()` is < 50 lines (currently 157)
- [ ] Each helper function has a single, clear responsibility
- [ ] Each helper function is independently testable
- [ ] Unit tests added for each new function
- [ ] All existing integration tests still pass
- [ ] Error handling behavior is unchanged
- [ ] API responses are identical to before
- [ ] No breaking changes to the API

## File to Modify
- `src/orac_stt/api/stt.py` - Lines 199-356 (the `_transcribe_impl` function)

## Git Commit Message Template
```
refactor: decompose monolithic transcription function

- Extract load_and_validate_audio() for audio processing
- Extract transcribe_with_error_handling() for ML inference
- Extract add_to_command_history() for history management
- Extract forward_to_core_async() for Core integration
- Extract build_transcription_response() for response building
- Add TranscriptionResult dataclass for intermediate state
- Add handle_validation_error() and handle_unexpected_error()
- Add unit tests for each extracted function

Reduces _transcribe_impl from 157 lines to ~40 lines
Each step now independently testable

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Notes
- This refactoring should NOT change any API behavior
- Error handling must work exactly the same way
- Command buffer recording must happen in all cases
- Debug recordings must still be saved
- All logging must be preserved
- Focus on extraction first, optimization later

## References
- Current code: `src/orac_stt/api/stt.py:199-356`
- Cleanup plan: `cleanup_prompt.md` Task 2.2
- Technical debt analysis: `cleanup.md` Section 2.2
