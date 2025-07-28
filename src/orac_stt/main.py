"""Main application entry point for ORAC STT service."""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config.loader import load_config
from .config.settings import Settings
from .utils.logging import setup_logging, get_logger
from .api import health, metrics, stt, admin
from .core.shutdown import shutdown_handler


# Global settings instance
settings: Optional[Settings] = None
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global settings, logger
    
    # Startup
    logger.info("Starting ORAC STT Service", extra={"version": "0.1.0"})
    
    # Initialize components here (model loading, etc.)
    # Set up command buffer observer for WebSocket notifications
    from .api.admin import setup_command_observer
    setup_command_observer()
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ORAC STT Service")
    # Cleanup resources here
    

def create_app(config_path: Optional[Path] = None) -> FastAPI:
    """Create FastAPI application instance.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Configured FastAPI application
    """
    global settings, logger
    
    # Load configuration
    settings = load_config(config_path)
    
    # Setup logging
    setup_logging(settings)
    logger = get_logger(__name__)
    
    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        lifespan=lifespan
    )
    
    # Include routers
    app.include_router(health.router, tags=["health"])
    app.include_router(metrics.router, tags=["monitoring"])
    app.include_router(stt.router, prefix="/stt/v1", tags=["stt"])
    app.include_router(admin.router, prefix="/admin", tags=["admin"])
    
    # Mount static files
    static_dir = Path(__file__).parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"Mounted static files from {static_dir}")
    else:
        logger.warning(f"Static directory not found: {static_dir}")
    
    return app


def main():
    """Main entry point for running the application."""
    global settings
    
    # Create application
    app = create_app()
    
    # Get settings for server configuration
    if settings is None:
        settings = load_config()
    
    # Configure SSL if enabled
    ssl_keyfile = None
    ssl_certfile = None
    if settings.security.enable_tls:
        ssl_keyfile = str(settings.security.key_file)
        ssl_certfile = str(settings.security.cert_file)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run server
    uvicorn.run(
        app,
        host=settings.api.host,
        port=settings.api.port,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
        log_config=None  # We handle logging ourselves
    )


if __name__ == "__main__":
    main()