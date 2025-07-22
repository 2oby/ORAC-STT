"""Graceful shutdown handling."""

import asyncio
import signal
from typing import Optional, Set

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ShutdownHandler:
    """Handle graceful shutdown of the application."""
    
    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._tasks: Set[asyncio.Task] = set()
        
    def register_task(self, task: asyncio.Task) -> None:
        """Register a task to be cancelled on shutdown."""
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
        
    def trigger_shutdown(self) -> None:
        """Trigger application shutdown."""
        logger.info("Triggering graceful shutdown")
        self._shutdown_event.set()
        
    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("Starting cleanup process")
        
        # Cancel all registered tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        logger.info("Cleanup complete")


# Global shutdown handler instance
shutdown_handler = ShutdownHandler()