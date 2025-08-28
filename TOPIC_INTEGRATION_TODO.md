# ORAC STT - Topic Integration TODO

**Created**: 2025-08-28  
**Related**: [`/TOPIC_MVP_IMPLEMENTATION.md`](../../TOPIC_MVP_IMPLEMENTATION.md)

## Overview
This document outlines the required changes to ORAC STT to support the ORAC Topic System MVP by accepting and forwarding topic parameters.

## Required Changes

### 1. API Endpoint Modification
**Location**: `src/orac_stt/api/stt.py`

#### Current Endpoint:
```python
@router.post("/stt/v1/stream")
async def stream_transcribe(file: UploadFile = File(...)):
    # Current implementation
```

#### New Endpoint with Topic Support:
```python
@router.post("/stt/v1/stream/{topic}")
async def stream_transcribe_with_topic(
    topic: str,
    file: UploadFile = File(...)
):
    # Implementation with topic forwarding
```

#### Tasks:
- [ ] Add new endpoint with topic path parameter
- [ ] Keep original endpoint for backward compatibility
- [ ] Default to "general" topic when not specified
- [ ] Validate topic name format (alphanumeric + underscore)

### 2. ORAC Core Integration
**Location**: `src/orac_stt/integrations/` (create if doesn't exist)

#### Create Core Client:
```python
# src/orac_stt/integrations/orac_core_client.py
import aiohttp
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ORACCoreClient:
    def __init__(self, base_url: str = "http://192.168.8.191:8000"):
        self.base_url = base_url
    
    async def forward_transcription(
        self, 
        text: str, 
        topic: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Forward transcription to ORAC Core with topic"""
        url = f"{self.base_url}/v1/generate/{topic}"
        
        payload = {
            "prompt": text,
            "metadata": metadata or {}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Forwarded to ORAC Core with topic '{topic}'")
                        return result
                    else:
                        logger.error(f"ORAC Core returned {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Failed to forward to ORAC Core: {e}")
            return None
```

#### Tasks:
- [ ] Create ORAC Core client class
- [ ] Implement transcription forwarding with topic
- [ ] Handle connection errors gracefully
- [ ] Add retry logic for failed requests
- [ ] Include metadata (confidence, language, duration)

### 3. Update Main STT Handler
**Location**: `src/orac_stt/api/stt.py`

#### Modified Implementation:
```python
from fastapi import APIRouter, File, UploadFile, HTTPException, Path
from typing import Optional
from ..integrations.orac_core_client import ORACCoreClient

router = APIRouter()
core_client = ORACCoreClient()

@router.post("/stt/v1/stream/{topic}")
async def stream_transcribe_with_topic(
    topic: str = Path(..., description="Topic for ORAC Core processing"),
    file: UploadFile = File(...)
):
    """Transcribe audio and forward to ORAC Core with specific topic"""
    
    # Validate topic name
    if not topic.replace('_', '').replace('-', '').isalnum():
        raise HTTPException(400, "Invalid topic name")
    
    # Existing transcription logic
    audio_data = await file.read()
    transcription = await transcribe_audio(audio_data)
    
    # Forward to ORAC Core with topic
    core_response = None
    if settings.forward_to_core:
        core_response = await core_client.forward_transcription(
            text=transcription['text'],
            topic=topic,
            metadata={
                'language': transcription.get('language'),
                'confidence': transcription.get('confidence'),
                'duration': transcription.get('duration')
            }
        )
    
    return {
        "text": transcription['text'],
        "confidence": transcription.get('confidence'),
        "language": transcription.get('language'),
        "topic": topic,
        "core_response": core_response
    }

# Backward compatibility endpoint
@router.post("/stt/v1/stream")
async def stream_transcribe(file: UploadFile = File(...)):
    """Legacy endpoint - defaults to 'general' topic"""
    return await stream_transcribe_with_topic(topic="general", file=file)
```

### 4. Configuration Updates
**Location**: `config.toml` or `src/orac_stt/config/settings.py`

#### Tasks:
- [ ] Add ORAC Core integration settings
- [ ] Configure Core URL and timeout
- [ ] Enable/disable forwarding flag
- [ ] Default topic configuration

#### Configuration Example:
```toml
[orac_core]
enabled = true
url = "http://192.168.8.191:8000"
timeout = 30
default_topic = "general"
retry_attempts = 3
```

### 5. Response Model Updates
**Location**: `src/orac_stt/models/` (if using Pydantic models)

#### Tasks:
- [ ] Add topic field to response models
- [ ] Include Core response in output
- [ ] Update OpenAPI documentation

```python
from pydantic import BaseModel
from typing import Optional, Any

class TranscriptionResponse(BaseModel):
    text: str
    confidence: float
    language: str
    duration: float
    processing_time: float
    topic: str = "general"
    core_response: Optional[Any] = None
```

### 6. Admin Interface Updates
**Location**: `src/orac_stt/web/templates/admin.html`

#### Tasks:
- [ ] Display topic in transcription history
- [ ] Show topic statistics
- [ ] Add topic filter to history view

### 7. Testing Requirements

#### Unit Tests:
- [ ] Test topic path parameter parsing
- [ ] Test invalid topic name validation
- [ ] Test Core forwarding with topic
- [ ] Test backward compatibility endpoint

#### Integration Tests:
- [ ] Test full flow: Hey ORAC → STT → Core with topic
- [ ] Test auto-discovery of new topics
- [ ] Test fallback to general topic
- [ ] Test error handling when Core is unavailable

#### Manual Testing:
```bash
# Test with specific topic
curl -X POST http://192.168.8.191:7272/stt/v1/stream/home_assistant \
  -F "file=@test_audio.wav"

# Test legacy endpoint (should use general topic)
curl -X POST http://192.168.8.191:7272/stt/v1/stream \
  -F "file=@test_audio.wav"

# Test with new auto-discovered topic
curl -X POST http://192.168.8.191:7272/stt/v1/stream/kitchen_helper \
  -F "file=@test_audio.wav"
```

## Logging Enhancements

#### Tasks:
- [ ] Log topic with each transcription
- [ ] Track topic usage metrics
- [ ] Log Core forwarding success/failure

```python
logger.info(f"Transcription completed for topic '{topic}': {text[:50]}...")
logger.debug(f"Forwarding to Core with topic '{topic}'")
```

## Backward Compatibility

- [ ] Original `/stt/v1/stream` endpoint continues to work
- [ ] Missing topic defaults to "general"
- [ ] Graceful handling if Core doesn't support topics yet
- [ ] No breaking changes to existing integrations

## Deployment Steps

1. Update ORAC STT code with topic support
2. Test locally with mock requests
3. Deploy to server (192.168.8.191:7272)
4. Test integration with Hey ORAC and ORAC Core
5. Monitor logs for any issues

## Success Criteria

- [ ] STT accepts topic as path parameter
- [ ] Topic is correctly forwarded to ORAC Core
- [ ] Legacy endpoint still works (backward compatibility)
- [ ] Auto-discovery works for new topics
- [ ] No performance degradation
- [ ] Proper error handling and logging

## Performance Considerations

- [ ] Topic routing should add minimal latency (<10ms)
- [ ] Core forwarding should be asynchronous
- [ ] Failed Core requests shouldn't block STT response
- [ ] Connection pooling for Core requests

## Timeline

Estimated: 1 day of development
- 2 hours: API endpoint modifications
- 2 hours: Core integration client
- 2 hours: Testing and validation
- 2 hours: Deployment and monitoring

## Notes

- Path parameters are cleaner than query parameters
- Topic enables different AI behaviors downstream
- Auto-discovery means flexible topic creation
- Maintain backward compatibility throughout

---

**Status**: Ready for Implementation  
**Priority**: High (required for Topic System MVP)  
**Dependencies**: ORAC Core must support `/v1/generate/{topic}` endpoint