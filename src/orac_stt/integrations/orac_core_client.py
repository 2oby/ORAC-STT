"""ORAC Core integration client for forwarding transcriptions with topic support."""

import aiohttp
from typing import Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ORACCoreClient:
    """Client for forwarding transcriptions to ORAC Core with topic support."""
    
    def __init__(self, base_url: str = "http://192.168.8.191:8000", timeout: int = 30):
        """Initialize ORAC Core client.
        
        Args:
            base_url: Base URL for ORAC Core API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session
    
    async def forward_transcription(
        self, 
        text: str, 
        topic: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Forward transcription to ORAC Core with topic.
        
        Args:
            text: Transcribed text to forward
            topic: Topic ID for routing (default: "general")
            metadata: Optional metadata (confidence, language, duration, etc.)
            
        Returns:
            Response from ORAC Core or None if failed
        """
        # Validate topic name (alphanumeric + underscore)
        if not topic or not topic.replace('_', '').isalnum():
            logger.warning(f"Invalid topic name '{topic}', using 'general'")
            topic = "general"
        
        url = f"{self.base_url}/v1/generate/{topic}"
        
        # Build payload
        payload = {
            "prompt": text,
            "stream": False
        }
        
        # Add metadata to payload if provided
        if metadata:
            payload["metadata"] = {
                **metadata,
                "source": "orac_stt",
                "timestamp": datetime.now().isoformat()
            }
        
        logger.info(f"Forwarding transcription to ORAC Core: topic='{topic}', text_length={len(text)}")
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Successfully forwarded to ORAC Core with topic '{topic}'")
                    return result
                elif response.status == 404:
                    logger.warning(f"Topic '{topic}' not found on ORAC Core")
                    # Auto-discovery should handle this on Core side
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"ORAC Core returned {response.status}: {error_text}")
                    return None
                    
        except aiohttp.ClientTimeout:
            logger.error(f"Timeout forwarding to ORAC Core (topic: {topic})")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Connection error forwarding to ORAC Core: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error forwarding to ORAC Core: {e}", exc_info=True)
            return None
    
    async def check_health(self) -> bool:
        """Check if ORAC Core is healthy.
        
        Returns:
            True if Core is healthy, False otherwise
        """
        url = f"{self.base_url}/v1/status"
        
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("status") == "running"
                return False
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()