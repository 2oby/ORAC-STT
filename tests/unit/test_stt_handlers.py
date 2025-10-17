"""Unit tests for STT handler functions.

Tests for the extracted helper functions from src/orac_stt/api/stt.py
These functions were extracted from the monolithic _transcribe_impl function
to improve testability and maintainability.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from io import BytesIO

from src.orac_stt.api.stt import (
    TranscriptionResult,
    load_and_validate_audio,
    transcribe_with_error_handling,
    add_to_command_history,
    forward_to_core_async,
    build_transcription_response,
    handle_validation_error,
    handle_unexpected_error,
    TranscriptionResponse
)
from src.orac_stt.audio.validator import AudioValidationError
from src.orac_stt.history.command_buffer import CommandBuffer


class TestTranscriptionResult:
    """Test TranscriptionResult dataclass."""

    def test_should_forward_success_case(self):
        """Test that successful transcriptions should be forwarded."""
        result = TranscriptionResult(
            text="hello world",
            confidence=0.95,
            language="en",
            has_error=False
        )
        assert result.should_forward is True

    def test_should_forward_error_case(self):
        """Test that errors should not be forwarded."""
        result = TranscriptionResult(
            text="",
            confidence=0.0,
            language="unknown",
            has_error=True,
            error_message="Test error"
        )
        assert result.should_forward is False

    def test_should_forward_empty_text(self):
        """Test that empty text should not be forwarded."""
        result = TranscriptionResult(
            text="   ",
            confidence=0.95,
            language="en",
            has_error=False
        )
        assert result.should_forward is False

    def test_should_forward_error_message_text(self):
        """Test that error message text (starting with '[') should not be forwarded."""
        result = TranscriptionResult(
            text="[Error occurred]",
            confidence=0.0,
            language="en",
            has_error=False
        )
        assert result.should_forward is False

    def test_get_metadata(self):
        """Test metadata dictionary generation."""
        result = TranscriptionResult(
            text="test",
            confidence=0.85,
            language="en",
            has_error=False
        )
        metadata = result.get_metadata(duration=2.5, processing_time=0.3)

        assert metadata["confidence"] == 0.85
        assert metadata["language"] == "en"
        assert metadata["duration"] == 2.5
        assert metadata["processing_time"] == 0.3


class TestLoadAndValidateAudio:
    """Test load_and_validate_audio function."""

    @pytest.mark.asyncio
    async def test_load_valid_audio(self):
        """Test loading valid audio file."""
        # Create a mock UploadFile with valid audio data
        mock_file = AsyncMock()
        mock_file.filename = "test.wav"

        # Generate simple sine wave audio (1 second at 16kHz)
        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_samples = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        # Mock the read to return valid audio bytes
        # For this test, we'll need to mock the AudioProcessor
        with patch('src.orac_stt.api.stt.AudioProcessor') as MockProcessor:
            mock_processor = MockProcessor.return_value
            mock_processor.load_audio.return_value = (audio_samples, sample_rate)
            mock_processor.get_audio_duration.return_value = duration
            mock_processor.prepare_for_whisper.return_value = audio_samples

            mock_file.read.return_value = b"mock_audio_data"

            audio_data, sr, dur = await load_and_validate_audio(mock_file)

            assert len(audio_data) == len(audio_samples)
            assert sr == sample_rate
            assert dur == duration
            mock_processor.load_audio.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_invalid_audio_raises_error(self):
        """Test that invalid audio raises AudioValidationError."""
        mock_file = AsyncMock()
        mock_file.filename = "invalid.txt"
        mock_file.read.return_value = b"not audio data"

        with patch('src.orac_stt.api.stt.AudioProcessor') as MockProcessor:
            mock_processor = MockProcessor.return_value
            mock_processor.load_audio.side_effect = AudioValidationError("Invalid format")

            with pytest.raises(AudioValidationError):
                await load_and_validate_audio(mock_file)


class TestTranscribeWithErrorHandling:
    """Test transcribe_with_error_handling function."""

    @pytest.mark.asyncio
    async def test_successful_transcription(self):
        """Test successful transcription returns TranscriptionResult."""
        audio_data = np.random.randn(16000).astype(np.float32)
        sample_rate = 16000
        mock_loader = Mock()

        with patch('src.orac_stt.api.stt.transcribe_audio') as mock_transcribe:
            mock_transcribe.return_value = {
                "text": "hello world",
                "confidence": 0.95,
                "language": "en"
            }

            result = await transcribe_with_error_handling(
                audio_data, sample_rate, mock_loader, "en", "transcribe", 0.0
            )

            assert result.text == "hello world"
            assert result.confidence == 0.95
            assert result.language == "en"
            assert result.has_error is False
            assert result.error_message is None

    @pytest.mark.asyncio
    async def test_transcription_error_handling(self):
        """Test that transcription errors are caught and returned as TranscriptionResult."""
        audio_data = np.random.randn(16000).astype(np.float32)
        sample_rate = 16000
        mock_loader = Mock()

        with patch('src.orac_stt.api.stt.transcribe_audio') as mock_transcribe:
            mock_transcribe.side_effect = Exception("Model error")

            result = await transcribe_with_error_handling(
                audio_data, sample_rate, mock_loader, "en", "transcribe", 0.0
            )

            assert "[Transcription Failed:" in result.text
            assert result.confidence == 0.0
            assert result.language == "unknown"
            assert result.has_error is True
            assert result.error_message == "Model error"


class TestAddToCommandHistory:
    """Test add_to_command_history function."""

    @pytest.mark.asyncio
    async def test_add_successful_command(self):
        """Test adding successful command to buffer."""
        buffer = CommandBuffer(max_size=5)

        await add_to_command_history(
            command_buffer=buffer,
            text="test command",
            audio_path=None,
            duration=1.5,
            confidence=0.95,
            processing_time=0.3,
            language="en",
            has_error=False,
            error_message=None
        )

        commands = buffer.get_commands()
        assert len(commands) == 1
        assert commands[0].text == "test command"
        assert commands[0].confidence == 0.95
        assert commands[0].has_error is False

    @pytest.mark.asyncio
    async def test_add_error_command(self):
        """Test adding error command to buffer."""
        buffer = CommandBuffer(max_size=5)

        await add_to_command_history(
            command_buffer=buffer,
            text="[Error occurred]",
            audio_path=None,
            duration=0.0,
            confidence=0.0,
            processing_time=0.1,
            language="unknown",
            has_error=True,
            error_message="Test error"
        )

        commands = buffer.get_commands()
        assert len(commands) == 1
        assert commands[0].text == "[Error occurred]"
        assert commands[0].has_error is True
        assert commands[0].error_message == "Test error"

    @pytest.mark.asyncio
    async def test_add_empty_text_uses_default(self):
        """Test that empty text is replaced with default message."""
        buffer = CommandBuffer(max_size=5)

        await add_to_command_history(
            command_buffer=buffer,
            text="",
            audio_path=None,
            duration=1.0,
            confidence=0.0,
            processing_time=0.2,
            language="en",
            has_error=False,
            error_message=None
        )

        commands = buffer.get_commands()
        assert len(commands) == 1
        assert commands[0].text == "[No transcription]"


class TestForwardToCoreAsync:
    """Test forward_to_core_async function."""

    @pytest.mark.asyncio
    async def test_forward_creates_task(self):
        """Test that forwarding creates an async task."""
        mock_client = Mock()
        mock_client.forward_transcription = AsyncMock()

        metadata = {"confidence": 0.95, "language": "en"}

        with patch('src.orac_stt.api.stt.asyncio.create_task') as mock_create_task:
            await forward_to_core_async(
                core_client=mock_client,
                text="test",
                topic="general",
                metadata=metadata
            )

            # Verify create_task was called
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_handles_errors(self):
        """Test that forwarding errors are caught and logged."""
        mock_client = Mock()
        mock_client.forward_transcription = AsyncMock(side_effect=Exception("Network error"))

        metadata = {"confidence": 0.95, "language": "en"}

        # Should not raise - errors are caught and logged
        await forward_to_core_async(
            core_client=mock_client,
            text="test",
            topic="general",
            metadata=metadata
        )


class TestBuildTranscriptionResponse:
    """Test build_transcription_response function."""

    def test_build_response_success(self):
        """Test building response from successful result."""
        result = TranscriptionResult(
            text="hello",
            confidence=0.95,
            language="en",
            has_error=False
        )

        response = build_transcription_response(result, 2.5, 0.3)

        assert isinstance(response, TranscriptionResponse)
        assert response.text == "hello"
        assert response.confidence == 0.95
        assert response.language == "en"
        assert response.duration == 2.5
        assert response.processing_time == 0.3

    def test_build_response_error(self):
        """Test building response from error result."""
        result = TranscriptionResult(
            text="[Error]",
            confidence=0.0,
            language="unknown",
            has_error=True,
            error_message="Test error"
        )

        response = build_transcription_response(result, 0.0, 0.1)

        assert isinstance(response, TranscriptionResponse)
        assert response.text == ""  # Empty for errors
        assert response.confidence == 0.0
        assert response.language == "unknown"
        assert response.duration == 0.0
        assert response.processing_time == 0.1


class TestHandleValidationError:
    """Test handle_validation_error function."""

    def test_handle_validation_error(self):
        """Test handling validation error."""
        buffer = CommandBuffer(max_size=5)
        error = AudioValidationError("Invalid format")

        response = handle_validation_error(error, buffer, 0.1)

        assert isinstance(response, TranscriptionResponse)
        assert response.text == ""
        assert response.confidence == 0.0
        assert response.duration == 0.0

        # Check that error was added to buffer
        commands = buffer.get_commands()
        assert len(commands) == 1
        assert commands[0].has_error is True
        assert "Invalid Audio" in commands[0].text


class TestHandleUnexpectedError:
    """Test handle_unexpected_error function."""

    def test_handle_unexpected_error(self):
        """Test handling unexpected error."""
        buffer = CommandBuffer(max_size=5)
        error = Exception("Unexpected error")

        response = handle_unexpected_error(error, buffer, 0.2)

        assert isinstance(response, TranscriptionResponse)
        assert response.text == ""
        assert response.confidence == 0.0
        assert response.duration == 0.0

        # Check that error was added to buffer
        commands = buffer.get_commands()
        assert len(commands) == 1
        assert commands[0].has_error is True
        assert "Processing Error" in commands[0].text
