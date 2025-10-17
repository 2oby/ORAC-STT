"""Unit tests for CommandBuffer."""

import pytest
from pathlib import Path
from orac_stt.history.command_buffer import CommandBuffer


def test_command_buffer_initialization():
    """Test CommandBuffer initialization."""
    buffer = CommandBuffer(max_size=3)
    assert buffer.max_size == 3
    assert len(buffer.get_commands()) == 0


def test_add_command():
    """Test adding a command to the buffer."""
    buffer = CommandBuffer(max_size=3)
    buffer.add_command(
        text="test command",
        duration=1.0,
        confidence=0.95
    )
    commands = buffer.get_commands()
    assert len(commands) == 1
    assert commands[0].text == "test command"
    assert commands[0].confidence == 0.95


def test_circular_buffer_behavior():
    """Test that buffer maintains max_size as circular buffer."""
    buffer = CommandBuffer(max_size=2)
    buffer.add_command(text="cmd1", duration=1.0, confidence=0.9)
    buffer.add_command(text="cmd2", duration=1.0, confidence=0.9)
    buffer.add_command(text="cmd3", duration=1.0, confidence=0.9)

    commands = buffer.get_commands()
    assert len(commands) == 2
    assert commands[0].text == "cmd2"
    assert commands[1].text == "cmd3"


def test_add_command_with_audio_path():
    """Test adding command with audio path."""
    buffer = CommandBuffer(max_size=3)
    audio_path = Path("/tmp/test_audio.wav")

    buffer.add_command(
        text="test with audio",
        duration=2.5,
        confidence=0.88,
        audio_path=audio_path
    )

    commands = buffer.get_commands()
    assert len(commands) == 1
    assert commands[0].audio_path == audio_path


def test_get_commands_returns_copy():
    """Test that get_commands returns a copy, not reference."""
    buffer = CommandBuffer(max_size=3)
    buffer.add_command(text="cmd1", duration=1.0, confidence=0.9)

    commands1 = buffer.get_commands()
    commands2 = buffer.get_commands()

    # Should be equal but not the same object
    assert commands1[0].text == commands2[0].text
    assert commands1 is not commands2
