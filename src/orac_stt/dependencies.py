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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings (cached singleton).

    Returns:
        Settings instance loaded from config.toml
    """
    return load_config()


@lru_cache(maxsize=1)
def get_model_loader(settings: Settings = Depends(get_settings)) -> UnifiedWhisperLoader:
    """Get or create model loader (cached singleton).

    Args:
        settings: Application settings (injected)

    Returns:
        UnifiedWhisperLoader instance
    """
    logger.info("Initializing model loader")
    return UnifiedWhisperLoader(settings.model)


@lru_cache(maxsize=1)
def get_command_buffer() -> CommandBuffer:
    """Get or create command buffer (cached singleton).

    Returns:
        CommandBuffer instance with max_size=5
    """
    logger.info("Initializing command buffer")
    return CommandBuffer(max_size=5)


@lru_cache(maxsize=1)
def get_core_client(settings: Settings = Depends(get_settings)) -> ORACCoreClient:
    """Get or create ORAC Core client (cached singleton).

    Args:
        settings: Application settings (injected)

    Returns:
        ORACCoreClient instance
    """
    # Use ORAC Core URL from config or default
    core_url = getattr(settings, 'orac_core_url', 'http://192.168.8.192:8000')
    logger.info(f"Initializing ORAC Core client: {core_url}")
    return ORACCoreClient(base_url=core_url)
