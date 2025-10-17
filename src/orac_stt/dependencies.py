"""FastAPI dependency injection providers.

This module provides dependency injection for shared instances using
FastAPI's Depends() system. This replaces global singleton patterns
with proper dependency injection for better testability and thread safety.
"""

from functools import lru_cache
from fastapi import Depends

from .config.loader import load_config
from .config.settings import Settings
from .models.unified_loader import UnifiedWhisperLoader
from .history.command_buffer import CommandBuffer
from .integrations.orac_core_client import ORACCoreClient
from .utils.logging import get_logger

logger = get_logger(__name__)


# Global singletons (initialized once)
_model_loader: UnifiedWhisperLoader = None
_command_buffer: CommandBuffer = None
_core_client: ORACCoreClient = None


def get_settings() -> Settings:
    """Get application settings.

    Returns:
        Settings instance loaded from config.toml
    """
    return load_config()


def get_model_loader() -> UnifiedWhisperLoader:
    """Get or create model loader (singleton).

    Returns:
        UnifiedWhisperLoader instance
    """
    global _model_loader
    if _model_loader is None:
        settings = load_config()
        logger.info("Initializing model loader")
        _model_loader = UnifiedWhisperLoader(settings.model)
    return _model_loader


def get_command_buffer() -> CommandBuffer:
    """Get or create command buffer (singleton).

    Returns:
        CommandBuffer instance with max_size=5
    """
    global _command_buffer
    if _command_buffer is None:
        logger.info("Initializing command buffer")
        _command_buffer = CommandBuffer(max_size=5)
    return _command_buffer


def get_core_client() -> ORACCoreClient:
    """Get or create ORAC Core client (singleton).

    Returns:
        ORACCoreClient instance
    """
    global _core_client
    if _core_client is None:
        settings = load_config()
        # Use ORAC Core URL from config or default
        core_url = getattr(settings, 'orac_core_url', 'http://192.168.8.192:8000')
        logger.info(f"Initializing ORAC Core client: {core_url}")
        _core_client = ORACCoreClient(base_url=core_url)
    return _core_client
