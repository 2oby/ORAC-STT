"""Shared pytest fixtures for ORAC STT tests."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def test_audio_dir():
    """Return path to test audio samples directory."""
    return Path(__file__).parent / "fixtures" / "audio_samples"


@pytest.fixture
def test_config_dir():
    """Return path to test config directory."""
    return Path(__file__).parent / "fixtures" / "config"


@pytest.fixture
def test_client():
    """Return FastAPI test client."""
    # Import here to avoid circular dependencies
    from orac_stt.main import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_settings():
    """Return mock settings for testing."""
    from orac_stt.config.settings import Settings, ModelConfig, APIConfig

    return Settings(
        model=ModelConfig(
            name="whisper-tiny",
            device="cpu",
            cache_dir=Path("/tmp/test_models")
        ),
        api=APIConfig(
            host="127.0.0.1",
            port=7272
        )
    )
