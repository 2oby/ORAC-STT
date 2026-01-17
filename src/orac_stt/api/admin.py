"""Admin API endpoints for ORAC STT management interface."""

import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl

from ..config.loader import load_config
from ..core.settings_manager import get_settings_manager
from ..models.unified_loader import UnifiedWhisperLoader
from ..utils.logging import get_logger
from .stt import get_model_loader, get_command_buffer
import aiohttp

router = APIRouter()
logger = get_logger(__name__)

# Store WebSocket connections
active_connections: List[WebSocket] = []


class ModelInfo(BaseModel):
    """Model information response."""
    name: str
    current: bool
    size_mb: Optional[float]
    description: str


class ModelSelectRequest(BaseModel):
    """Model selection request."""
    model_name: str


class ORACCoreConfig(BaseModel):
    """ORAC Core configuration."""
    orac_core_url: str
    timeout: int = 30


class ORACCoreConfigRequest(BaseModel):
    """ORAC Core configuration request."""
    orac_core_url: str
    timeout: Optional[int] = 30


class ConfigTestResponse(BaseModel):
    """Configuration test response."""
    success: bool
    message: str
    url: str


# Model descriptions and sizes
MODEL_INFO = {
    "whisper-tiny": {
        "size_mb": 75,
        "description": "Fastest inference, basic accuracy"
    },
    "whisper-base": {
        "size_mb": 142,
        "description": "Good balance of speed/accuracy"
    },
    "whisper-small": {
        "size_mb": 466,
        "description": "Better accuracy, slower"
    },
    "whisper-medium": {
        "size_mb": 1500,
        "description": "Best accuracy, much slower"
    }
}


@router.get("/")
async def admin_dashboard():
    """Serve the admin dashboard HTML."""
    html_path = Path(__file__).parent.parent / "web" / "templates" / "admin.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text())
    else:
        # Return inline HTML if template not found
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ORAC STT Admin</title>
        </head>
        <body>
            <h1>ORAC STT Admin Dashboard</h1>
            <p>Template not found. Please create src/orac_stt/web/templates/admin.html</p>
        </body>
        </html>
        """)


@router.get("/models", response_model=List[ModelInfo])
async def list_models() -> List[ModelInfo]:
    """List available whisper models."""
    model_loader = get_model_loader()
    current_model = model_loader.config.name
    
    models = []
    for model_name, info in MODEL_INFO.items():
        models.append(ModelInfo(
            name=model_name,
            current=(model_name == current_model),
            size_mb=info["size_mb"],
            description=info["description"]
        ))
    
    return models


@router.post("/models/select")
async def select_model(request: ModelSelectRequest) -> Dict[str, str]:
    """Switch to a different whisper model.

    Note: When using whisper-server backend, changing models requires a container
    restart since the server loads the model at startup. This endpoint updates
    the configuration but the actual model change takes effect after restart.
    """
    model_name = request.model_name

    if model_name not in MODEL_INFO:
        raise HTTPException(status_code=400, detail=f"Invalid model: {model_name}")

    try:
        # Get current model loader
        model_loader = get_model_loader()
        current_model = model_loader.config.name

        # Check if using whisper-server (requires restart for model change)
        if model_loader.use_whisper_server:
            logger.info(f"Model selection changed: {current_model} -> {model_name}")
            logger.info("Note: whisper-server requires container restart for model change")

            # Update the in-memory config name (for display purposes)
            # The actual whisper-server will continue using its loaded model
            # until container restart with new MODEL_NAME env var

            # Notify connected clients
            await notify_model_change(model_name)

            return {
                "status": "restart_required",
                "message": f"Model changed to {model_name}. Container restart required to apply.",
                "current_model": current_model,
                "selected_model": model_name,
                "instruction": "Update MODEL_NAME in docker-compose.yml and restart container"
            }

        # For non-server backends, hot-reload is possible
        # Update configuration
        model_loader.config.name = model_name

        # Clear current model to force reload
        model_loader._model = None

        # Preload new model
        logger.info(f"Switching to model: {model_name}")
        model_loader.load_model()

        # Notify connected clients
        await notify_model_change(model_name)

        return {"status": "success", "message": f"Switched to {model_name}"}

    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch model: {str(e)}")


class ModelRestartRequest(BaseModel):
    """Model restart request."""
    model_name: str


# Track the running model (set by entrypoint, updated on restart)
_running_model: Optional[str] = None


def _get_running_model() -> str:
    """Get the currently running model from whisper-server or config."""
    global _running_model
    if _running_model:
        return _running_model
    # Fall back to environment variable
    import os
    return os.environ.get("MODEL_NAME", "whisper-tiny")


def _set_running_model(model_name: str) -> None:
    """Set the running model name."""
    global _running_model
    _running_model = model_name


@router.get("/models/running")
async def get_running_model() -> Dict[str, str]:
    """Get the currently running whisper model."""
    return {
        "running_model": _get_running_model(),
        "config_model": get_model_loader().config.name
    }


@router.post("/models/restart")
async def restart_with_model(request: ModelRestartRequest) -> Dict[str, Any]:
    """Restart whisper-server with a new model.

    This kills the current whisper-server process and starts a new one
    with the specified model. Takes ~10-15 seconds.
    """
    import subprocess
    import os
    import time

    model_name = request.model_name

    if model_name not in MODEL_INFO:
        raise HTTPException(status_code=400, detail=f"Invalid model: {model_name}")

    # Map model name to ggml file
    model_files = {
        "whisper-tiny": "ggml-tiny.bin",
        "whisper-base": "ggml-base.bin",
        "whisper-small": "ggml-small.bin",
        "whisper-medium": "ggml-medium.bin",
    }

    ggml_file = model_files.get(model_name, "ggml-tiny.bin")
    model_path = f"/app/models/whisper_cpp/whisper/{ggml_file}"

    # Check if model file exists
    if not os.path.exists(model_path):
        raise HTTPException(
            status_code=400,
            detail=f"Model file not found: {model_path}"
        )

    logger.info(f"Restarting whisper-server with model: {model_name}")

    try:
        # Kill existing whisper-server
        logger.info("Stopping existing whisper-server...")
        subprocess.run(["pkill", "-f", "whisper-server"], timeout=5)
        time.sleep(1)  # Give it time to die

        # Start new whisper-server
        whisper_prompt = os.environ.get(
            "WHISPER_PROMPT",
            "lounge cabinet lights kitchen bedroom bathroom office"
        )

        cmd = [
            "/app/third_party/whisper_cpp/bin/whisper-server",
            "--model", model_path,
            "--host", "127.0.0.1",
            "--port", "8080",
            "--no-timestamps",
            "--language", "en",
            "--prompt", whisper_prompt
        ]

        logger.info(f"Starting whisper-server: {' '.join(cmd)}")

        # Start in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )

        # Wait for server to be ready (poll health endpoint)
        logger.info("Waiting for whisper-server to be ready...")
        for _ in range(60):  # Wait up to 60 seconds
            time.sleep(1)
            try:
                import urllib.request
                urllib.request.urlopen("http://127.0.0.1:8080/", timeout=2)
                logger.info("whisper-server is ready!")
                break
            except Exception:
                continue
        else:
            raise RuntimeError("whisper-server failed to start within 60 seconds")

        # Update running model tracker
        _set_running_model(model_name)

        # Update config
        model_loader = get_model_loader()
        model_loader.config.name = model_name

        # Notify clients
        await notify_model_change(model_name)

        return {
            "status": "success",
            "message": f"Restarted with {model_name}",
            "running_model": model_name
        }

    except subprocess.TimeoutExpired:
        logger.error("Timeout killing whisper-server")
        raise HTTPException(status_code=500, detail="Timeout stopping whisper-server")
    except Exception as e:
        logger.error(f"Failed to restart whisper-server: {e}")
        raise HTTPException(status_code=500, detail=f"Restart failed: {str(e)}")


@router.get("/commands")
async def get_commands(limit: int = 5) -> List[Dict[str, Any]]:
    """Get recent transcribed commands."""
    command_buffer = get_command_buffer()
    commands = command_buffer.get_commands(limit=limit)
    
    return [cmd.to_dict() for cmd in commands]


@router.get("/commands/{command_id}/audio")
async def get_command_audio(command_id: str):
    """Stream audio file for a specific command."""
    command_buffer = get_command_buffer()
    command = command_buffer.get_command(command_id)
    
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    
    if not command.audio_path or not command.audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    return FileResponse(
        command.audio_path,
        media_type="audio/wav",
        filename=f"command_{command_id}.wav"
    )


@router.get("/config/orac-core", response_model=ORACCoreConfig)
async def get_orac_core_config() -> ORACCoreConfig:
    """Get current ORAC Core configuration."""
    try:
        # Import here to avoid circular dependencies
        from ..integrations.orac_core_client import get_orac_core_client
        
        client = get_orac_core_client()
        return ORACCoreConfig(
            orac_core_url=client.base_url,
            timeout=int(client.timeout.total) if client.timeout else 30
        )
    except Exception as e:
        logger.error(f"Failed to get ORAC Core config: {e}")
        # Return default config if unable to get current
        return ORACCoreConfig(orac_core_url="http://192.168.8.192:8000", timeout=30)


@router.post("/config/orac-core")
async def set_orac_core_config(config: ORACCoreConfigRequest) -> Dict[str, Any]:
    """Set ORAC Core configuration and test connection."""
    try:
        # Import here to avoid circular dependencies
        from ..integrations.orac_core_client import update_orac_core_client
        import aiohttp
        
        # Validate URL format
        url = config.orac_core_url.rstrip('/')
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
        
        # Test connection to the new URL
        timeout = aiohttp.ClientTimeout(total=5)  # Quick test timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(f"{url}/v1/status") as response:
                    if response.status != 200:
                        logger.warning(f"ORAC Core health check returned {response.status}")
                        return {
                            "status": "warning",
                            "message": f"Configuration saved but ORAC Core returned status {response.status}",
                            "url": url,
                            "timeout": config.timeout
                        }
            except aiohttp.ClientError as e:
                logger.warning(f"ORAC Core connection test failed: {e}")
                return {
                    "status": "warning", 
                    "message": f"Configuration saved but connection test failed: {str(e)}",
                    "url": url,
                    "timeout": config.timeout
                }
        
        # Update the client configuration
        update_orac_core_client(url, config.timeout or 30)
        
        logger.info(f"Updated ORAC Core config: url={url}, timeout={config.timeout}")
        
        return {
            "status": "success",
            "message": "ORAC Core configuration updated successfully",
            "url": url,
            "timeout": config.timeout
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set ORAC Core config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.post("/config/orac-core/test")
async def test_orac_core_connection() -> Dict[str, Any]:
    """Test connection to currently configured ORAC Core."""
    try:
        from ..integrations.orac_core_client import get_orac_core_client
        
        client = get_orac_core_client()
        is_healthy = await client.check_health()
        
        if is_healthy:
            return {
                "status": "success",
                "message": "ORAC Core connection successful",
                "url": client.base_url
            }
        else:
            return {
                "status": "error", 
                "message": "ORAC Core is not responding or unhealthy",
                "url": client.base_url
            }
            
    except Exception as e:
        logger.error(f"ORAC Core connection test failed: {e}")
        return {
            "status": "error",
            "message": f"Connection test failed: {str(e)}",
            "url": "unknown"
        }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket connected. Total connections: {len(active_connections)}")
    
    try:
        # Send initial data
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to ORAC STT Admin"
        })
        
        # Keep connection alive
        while True:
            # Wait for any message from client (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Remaining connections: {len(active_connections)}")


async def notify_new_command(command_dict: Dict[str, Any]):
    """Notify all connected WebSocket clients of a new command."""
    if not active_connections:
        return
        
    message = {
        "type": "new_command",
        "command": command_dict
    }
    
    # Send to all connected clients
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)


async def notify_model_change(model_name: str):
    """Notify all connected WebSocket clients of model change."""
    if not active_connections:
        return
        
    message = {
        "type": "model_changed",
        "model": model_name
    }
    
    # Send to all connected clients
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)


# Set up command buffer observer when module loads
def setup_command_observer():
    """Set up observer to notify WebSocket clients of new commands."""
    try:
        command_buffer = get_command_buffer()
        
        def on_new_command(command):
            """Callback when new command is added."""
            # Use asyncio.run_coroutine_threadsafe for thread safety
            import asyncio
            try:
                # Try to get the running event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop, skip notification
                    logger.debug("No running event loop, skipping WebSocket notification")
                    return
                
                # Schedule the coroutine in the event loop thread-safely
                future = asyncio.run_coroutine_threadsafe(
                    notify_new_command(command.to_dict()), 
                    loop
                )
                # Don't wait for completion to avoid blocking
                
            except Exception as e:
                logger.error(f"Error scheduling WebSocket notification: {e}")
        
        command_buffer.add_observer(on_new_command)
        logger.info("Set up command buffer observer for WebSocket notifications")
    except Exception as e:
        logger.error(f"Failed to set up command observer: {e}")


