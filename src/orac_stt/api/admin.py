"""Admin API endpoints for ORAC STT management interface."""

import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from ..config.loader import load_config
from ..models.unified_loader import UnifiedWhisperLoader
from ..utils.logging import get_logger
from .stt import get_model_loader, get_command_buffer

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
    """Switch to a different whisper model."""
    model_name = request.model_name
    
    if model_name not in MODEL_INFO:
        raise HTTPException(status_code=400, detail=f"Invalid model: {model_name}")
    
    try:
        # Get current model loader
        model_loader = get_model_loader()
        
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
                # Get the current event loop
                loop = asyncio.get_event_loop()
                asyncio.run_coroutine_threadsafe(
                    notify_new_command(command.to_dict()), 
                    loop
                )
            except RuntimeError:
                # If no event loop, create task normally
                asyncio.create_task(notify_new_command(command.to_dict()))
        
        command_buffer.add_observer(on_new_command)
        logger.info("Set up command buffer observer for WebSocket notifications")
    except Exception as e:
        logger.error(f"Failed to set up command observer: {e}")