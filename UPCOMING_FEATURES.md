# ORAC STT - Upcoming Features & Enhancements

**Project:** ORAC STT (Speech-to-Text Service)
**Version:** 0.2.0
**Last Updated:** October 17, 2025

---

## Table of Contents

1. [Optimization & Performance](#optimization--performance)
2. [Real-time Streaming](#real-time-streaming)
3. [Advanced ML Features](#advanced-ml-features)
4. [Developer Experience](#developer-experience)
5. [Integration Enhancements](#integration-enhancements)
6. [Scalability Features](#scalability-features)

---

## Optimization & Performance

### 1. Model Preloading on Startup
**Status:** Planned | **Priority:** High | **Effort:** 1 day

**Problem:** First transcription request has higher latency due to lazy model loading.

**Solution:**
```python
# src/orac_stt/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global settings, logger

    # Startup
    logger.info("Starting ORAC STT Service", extra={"version": "0.2.0"})

    # Preload model to avoid first-request latency
    logger.info("Preloading whisper model...")
    model_loader = get_model_loader()
    await asyncio.get_event_loop().run_in_executor(
        None,
        model_loader.load_model
    )
    logger.info(f"Model preloaded: {model_loader.config.name}")

    # Set up command buffer observer for WebSocket notifications
    from .api.admin import setup_command_observer
    setup_command_observer()

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down ORAC STT Service")
    # Cleanup model resources
    if model_loader._model:
        del model_loader._model
```

**Benefits:**
- Eliminates first-request cold start
- Predictable latency from first request
- Better user experience on service restart

**Metrics to Track:**
- Time to ready (startup time)
- First request latency (before/after)

---

### 2. Connection Pooling for ORAC Core Client
**Status:** Planned | **Priority:** Medium | **Effort:** 2 days

**Problem:** Creating new HTTP connections for each transcription adds overhead.

**Solution:**
```python
# src/orac_stt/integrations/orac_core_client.py
import aiohttp

class ORACCoreClient:
    """HTTP client for forwarding transcriptions to ORAC Core."""

    def __init__(self, base_url: str, pool_size: int = 10, timeout: int = 30):
        self.base_url = base_url.rstrip('/')

        # Create session with connection pooling
        connector = aiohttp.TCPConnector(
            limit=pool_size,              # Max connections
            limit_per_host=pool_size,     # Max per host
            ttl_dns_cache=300,            # Cache DNS for 5 min
            keepalive_timeout=60          # Keep connections alive
        )

        timeout_config = aiohttp.ClientTimeout(
            total=timeout,
            connect=5,
            sock_read=timeout
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout_config,
            headers={
                "User-Agent": "ORAC-STT/0.2.0",
                "Accept": "application/json"
            }
        )
        self.logger = get_logger(__name__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Close session and cleanup connections."""
        if self._session:
            await self._session.close()

    async def forward_transcription(
        self,
        text: str,
        topic: str,
        metadata: dict
    ) -> dict:
        """Forward transcription to ORAC Core with connection reuse."""
        # Use existing session (connection pooling)
        async with self._session.post(
            f"{self.base_url}/command",
            json={
                "text": text,
                "topic": topic,
                "metadata": metadata
            }
        ) as response:
            response.raise_for_status()
            return await response.json()
```

**Update Dependencies:**
```python
# src/orac_stt/dependencies.py
_core_client: ORACCoreClient = None

def get_core_client() -> ORACCoreClient:
    """Get or create ORAC Core client (singleton with pooling)."""
    global _core_client
    if _core_client is None:
        settings = load_config()
        core_url = getattr(settings, 'orac_core_url', 'http://192.168.8.192:8000')
        logger.info(f"Initializing ORAC Core client with connection pool: {core_url}")
        _core_client = ORACCoreClient(
            base_url=core_url,
            pool_size=10,      # 10 concurrent connections
            timeout=30
        )
    return _core_client

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    global _core_client
    if _core_client:
        await _core_client.close()
```

**Benefits:**
- Reuse TCP connections (saves ~50-100ms per request)
- Better throughput under load
- Automatic connection management
- DNS caching reduces lookups

**Expected Impact:**
- 20-30% reduction in forwarding latency
- Better performance under concurrent load

---

### 3. GPU Batching for Concurrent Requests
**Status:** Research | **Priority:** Medium | **Effort:** 1-2 weeks

**Problem:** Processing multiple transcription requests sequentially underutilizes GPU.

**Concept:**
```python
# src/orac_stt/models/batch_processor.py
import asyncio
from collections import deque
from dataclasses import dataclass
from typing import List

@dataclass
class TranscriptionJob:
    """Represents a single transcription job."""
    audio_data: np.ndarray
    sample_rate: int
    language: str
    future: asyncio.Future

class BatchProcessor:
    """Batch multiple transcription requests for GPU efficiency."""

    def __init__(
        self,
        model_loader: UnifiedWhisperLoader,
        batch_size: int = 4,
        max_wait_ms: int = 100
    ):
        self.model_loader = model_loader
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms
        self.queue = deque()
        self.processing = False
        self.logger = get_logger(__name__)

    async def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        language: str = "en"
    ) -> dict:
        """Queue transcription and wait for batched result."""
        future = asyncio.Future()
        job = TranscriptionJob(audio_data, sample_rate, language, future)

        self.queue.append(job)

        # Start processing if not already running
        if not self.processing:
            asyncio.create_task(self._process_batch())

        # Wait for result
        return await future

    async def _process_batch(self):
        """Process queued jobs in batches."""
        self.processing = True

        try:
            # Wait briefly to collect more jobs
            await asyncio.sleep(self.max_wait_ms / 1000)

            # Collect batch
            batch = []
            while len(batch) < self.batch_size and self.queue:
                batch.append(self.queue.popleft())

            if not batch:
                return

            self.logger.info(f"Processing batch of {len(batch)} transcriptions")

            # Process all jobs in parallel (GPU batching)
            results = await self._batch_transcribe([j.audio_data for j in batch])

            # Resolve futures
            for job, result in zip(batch, results):
                job.future.set_result(result)

        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")
            # Fail all jobs in batch
            for job in batch:
                if not job.future.done():
                    job.future.set_exception(e)
        finally:
            self.processing = False

            # Continue processing if more jobs queued
            if self.queue:
                asyncio.create_task(self._process_batch())

    async def _batch_transcribe(self, audio_list: List[np.ndarray]) -> List[dict]:
        """Transcribe multiple audio files in one GPU call."""
        # This requires whisper.cpp to support batch inference
        # or processing them in parallel threads
        loop = asyncio.get_event_loop()

        # Run all transcriptions in parallel
        tasks = [
            loop.run_in_executor(
                None,
                self.model_loader.transcribe,
                audio,
                16000,
                "en",
                "transcribe"
            )
            for audio in audio_list
        ]

        return await asyncio.gather(*tasks)
```

**Note:** True GPU batching requires whisper.cpp to support batch inference at the model level. This implementation provides parallel processing, which gives some benefit but not full GPU batching.

**Benefits:**
- Higher GPU utilization
- Better throughput (requests/second)
- Reduced per-request latency under load

**Trade-offs:**
- Increased complexity
- Slightly higher latency for first request in batch (wait time)
- Only beneficial under concurrent load

---

### 4. Audio Preprocessing Optimization
**Status:** Planned | **Priority:** Low | **Effort:** 2-3 days

**Problem:** Audio loading and conversion can be slow for some formats.

**Solution:**
```python
# src/orac_stt/audio/processor.py
import subprocess
import tempfile

class AudioProcessor:
    """Optimized audio processing using ffmpeg."""

    def load_audio_fast(self, audio_bytes: bytes) -> tuple[np.ndarray, int]:
        """Fast audio loading using ffmpeg pipe."""

        # Use ffmpeg for fast conversion to 16kHz mono PCM
        # Much faster than librosa for format conversion
        process = subprocess.Popen(
            [
                'ffmpeg',
                '-i', 'pipe:0',           # Input from stdin
                '-f', 's16le',            # Output format: signed 16-bit little-endian
                '-acodec', 'pcm_s16le',   # Audio codec
                '-ar', '16000',           # Sample rate: 16kHz
                '-ac', '1',               # Channels: mono
                '-loglevel', 'quiet',     # Suppress output
                'pipe:1'                  # Output to stdout
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        out, err = process.communicate(input=audio_bytes)

        if process.returncode != 0:
            raise AudioValidationError(f"FFmpeg conversion failed: {err.decode()}")

        # Convert bytes to numpy array
        audio_data = np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0

        return audio_data, 16000
```

**Benefits:**
- 3-5x faster audio loading for compressed formats (MP3, AAC, OGG)
- Handles more audio formats automatically
- Lower CPU usage

**Requirements:**
- ffmpeg installed in container (already present)

---

### 5. Response Caching
**Status:** Planned | **Priority:** Low | **Effort:** 2 days

**Problem:** Identical audio files transcribed multiple times waste resources.

**Solution:**
```python
# src/orac_stt/cache/transcription_cache.py
import hashlib
from typing import Optional
from redis.asyncio import Redis

class TranscriptionCache:
    """Cache transcription results in Redis."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.ttl = 3600  # 1 hour cache

    def _hash_audio(self, audio_data: np.ndarray) -> str:
        """Generate deterministic hash of audio data."""
        # Hash the audio content
        return hashlib.sha256(audio_data.tobytes()).hexdigest()

    async def get(self, audio_data: np.ndarray, language: str) -> Optional[dict]:
        """Get cached transcription if available."""
        cache_key = f"transcript:{self._hash_audio(audio_data)}:{language}"
        cached = await self.redis.get(cache_key)

        if cached:
            return json.loads(cached)
        return None

    async def set(self, audio_data: np.ndarray, language: str, result: dict):
        """Cache transcription result."""
        cache_key = f"transcript:{self._hash_audio(audio_data)}:{language}"
        await self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(result)
        )

    async def clear(self):
        """Clear all cached transcriptions."""
        async for key in self.redis.scan_iter("transcript:*"):
            await self.redis.delete(key)

# Usage in STT endpoint
async def transcribe_with_cache(
    audio_data: np.ndarray,
    sample_rate: int,
    model_loader: UnifiedWhisperLoader,
    cache: TranscriptionCache,
    language: str = "en"
) -> dict:
    """Transcribe with caching."""

    # Check cache first
    cached = await cache.get(audio_data, language)
    if cached:
        logger.info("Cache hit - returning cached transcription")
        return cached

    # Cache miss - transcribe
    result = await transcribe_audio(audio_data, sample_rate, model_loader, language)

    # Store in cache
    await cache.set(audio_data, language, result)

    return result
```

**Benefits:**
- Instant response for duplicate audio
- Reduced GPU load
- Useful for testing/debugging scenarios

**Trade-offs:**
- Requires Redis
- Memory usage for cache
- Only helps with exact duplicates

---

## Real-time Streaming

### 🌟 WebSocket Streaming Transcription
**Status:** Planned | **Priority:** Medium | **Effort:** 2-3 weeks
**Note:** This is an ORAC-wide architectural change, not just ORAC STT

**Overview:**
Enable real-time, bidirectional streaming between Hey ORAC instances and ORAC STT for progressive transcription results.

**System-wide Impact:**
```
┌─────────────────────────────────────────────────────────────┐
│                     ORAC System Change                       │
├─────────────────────────────────────────────────────────────┤
│  Hey ORAC (RPi)     →  WebSocket  →  ORAC STT (Orin)       │
│  - Stream mic audio                  - Progressive results   │
│  - Display partial                   - Stream transcription  │
│                                                               │
│  ORAC STT (Orin)    →  WebSocket  →  ORAC Core             │
│  - Forward partial                   - Progressive LLM       │
│  - Send final                        - Early command detect  │
└─────────────────────────────────────────────────────────────┘
```

**Components Affected:**
1. **Hey ORAC** (Raspberry Pi client)
   - Replace HTTP POST with WebSocket client
   - Stream audio chunks instead of full file
   - Display partial transcriptions in real-time

2. **ORAC STT** (This service)
   - Add WebSocket endpoints
   - Implement streaming transcription
   - Buffer management and partial results

3. **ORAC Core** (LLM service)
   - Accept streaming transcriptions
   - Progressive command recognition
   - Early intent detection

**Benefits:**
- ✅ Lower perceived latency (partial results appear immediately)
- ✅ Better user experience (see transcription as you speak)
- ✅ Continuous listening mode (no reconnection overhead)
- ✅ Early command detection (Core can start processing before speech ends)
- ✅ Natural conversation flow

**Challenges:**
- ⚠️ whisper.cpp optimized for full-file, not streaming
- ⚠️ Need buffering and segmentation logic
- ⚠️ Requires coordination across 3 services
- ⚠️ Network reliability becomes critical
- ⚠️ State management complexity

**Implementation Phases:**

**Phase 1: ORAC STT WebSocket Support** (1 week)
```python
# src/orac_stt/api/websocket.py
@router.websocket("/ws/stream/{topic}")
async def websocket_stream_endpoint(
    websocket: WebSocket,
    topic: str,
    model_loader: UnifiedWhisperLoader = Depends(get_model_loader)
):
    await websocket.accept()

    audio_buffer = AudioStreamBuffer(chunk_size=16000)  # 1 second chunks

    try:
        while True:
            # Receive audio chunk
            data = await websocket.receive_bytes()
            audio_buffer.add(data)

            # Process when enough audio accumulated
            if audio_buffer.ready():
                chunk = audio_buffer.get_chunk()
                result = await transcribe_chunk(chunk)

                await websocket.send_json({
                    "type": "partial",
                    "text": result["text"],
                    "confidence": result["confidence"],
                    "timestamp": time.time()
                })

    except WebSocketDisconnect:
        # Process final buffer
        final = await audio_buffer.finalize()
        await websocket.send_json({
            "type": "final",
            "text": final["text"],
            "confidence": final["confidence"]
        })
```

**Phase 2: Hey ORAC Client Integration** (1 week)
- Modify Hey ORAC to use WebSocket for audio streaming
- Implement audio chunking (send 100-500ms chunks)
- Display partial transcriptions
- Fallback to HTTP if WebSocket unavailable

**Phase 3: ORAC Core Streaming Support** (1 week)
- Accept partial transcriptions from ORAC STT
- Implement progressive command parsing
- Early intent detection (trigger actions before sentence complete)
- Maintain conversation context

**Detailed Implementation Guide:**
See `docs/architecture/websocket-streaming-design.md` (to be created)

**Configuration:**
```toml
# config.toml
[websocket]
enabled = true
max_connections = 50
chunk_duration_ms = 500
buffer_seconds = 5
ping_interval = 30
```

**Metrics to Track:**
- WebSocket connections (active/total)
- Partial transcription latency
- Final transcription accuracy
- Network disconnection rate
- Reconnection success rate

---

## Advanced ML Features

### 1. Multi-Model Support
**Status:** Planned | **Priority:** Low | **Effort:** 2 weeks

Allow running multiple Whisper models simultaneously (e.g., tiny for speed, base for accuracy).

**Use Cases:**
- Quick preview with tiny model
- Accurate transcription with base model
- Compare model outputs

---

### 2. Custom Model Upload
**Status:** Research | **Priority:** Low | **Effort:** 3 weeks

Enable users to upload fine-tuned Whisper models.

**Requirements:**
- Model validation
- Version management
- A/B testing support

---

### 3. Speaker Diarization
**Status:** Research | **Priority:** Low | **Effort:** 3-4 weeks

Identify and label different speakers in audio.

**Approach:**
- Use pyannote.audio for diarization
- Combine with Whisper transcription
- Label transcript segments by speaker

---

## Developer Experience

### 1. Python Client SDK
**Status:** Planned | **Priority:** Medium | **Effort:** 1 week

```python
# Example usage
from orac_stt import Client

client = Client("http://orin-nano:7272", api_key="xxx")

# Simple transcription
result = await client.transcribe("audio.wav", topic="general")
print(result.text)

# Streaming transcription
async for partial in client.stream("audio.wav"):
    print(partial.text, end="\r")
```

---

### 2. Local Development Environment
**Status:** Planned | **Priority:** Medium | **Effort:** 3 days

Complete docker-compose setup for local development with all dependencies.

```yaml
# docker-compose.dev.yml
services:
  orac-stt:
    volumes:
      - ./src:/app/src:rw
    environment:
      - ORAC_LOG_LEVEL=DEBUG

  redis:
    image: redis:7-alpine

  postgres:
    image: postgres:15

  mock-orac-core:
    image: mockserver/mockserver
    # Mock ORAC Core for local testing
```

---

### 3. CLI Tools
**Status:** Planned | **Priority:** Low | **Effort:** 1 week

```bash
# Development CLI
orac-stt dev test-audio sample.wav           # Quick test
orac-stt dev benchmark                       # Run benchmarks
orac-stt dev clear-cache                     # Clear caches
orac-stt dev logs --follow --level=ERROR     # Stream logs

# Operations CLI
orac-stt ops health                          # Check health
orac-stt ops metrics                         # Show metrics
orac-stt ops topics list                     # List topics
orac-stt ops topics add computa --url=...    # Add topic
```

---

## Integration Enhancements

### 1. ORAC Core Enhanced Integration
**Status:** Planned | **Priority:** Medium | **Effort:** 1 week

**Features:**
- Bidirectional communication (Core can query STT)
- Confidence-based retry (Core requests re-transcription if low confidence)
- Context passing (send conversation history for better accuracy)

---

### 2. Home Assistant Integration
**Status:** Planned | **Priority:** Low | **Effort:** 2 weeks

Native Home Assistant integration for voice control.

```yaml
# configuration.yaml
stt:
  - platform: orac_stt
    host: 192.168.8.xxx
    port: 7272
    topic: home_assistant
```

---

### 3. Webhook Support
**Status:** Planned | **Priority:** Low | **Effort:** 3 days

Allow external services to receive transcription events.

```python
# POST to registered webhooks
{
  "event": "transcription.complete",
  "topic": "general",
  "text": "hello world",
  "confidence": 0.95,
  "timestamp": "2025-10-17T12:00:00Z"
}
```

---

## Scalability Features

### 1. Horizontal Scaling
**Status:** Planned | **Priority:** Medium | **Effort:** 1 week

Deploy multiple ORAC STT instances with load balancing.

**Requirements:**
- Shared Redis for cache
- Shared PostgreSQL for topics
- Load balancer (NGINX/HAProxy)

---

### 2. Queue-based Processing
**Status:** Planned | **Priority:** Medium | **Effort:** 1 week

Use Celery/RQ for asynchronous transcription jobs.

**Benefits:**
- Handle traffic spikes
- Background processing
- Job retry and monitoring

---

### 3. Edge Deployment
**Status:** Research | **Priority:** Low | **Effort:** 4+ weeks

Run lightweight version on Raspberry Pi (without GPU).

**Challenges:**
- Much slower CPU-only inference
- Limited model selection (tiny only)
- Memory constraints

---

## Priority Matrix

| Feature | Priority | Effort | Impact | Status |
|---------|----------|--------|--------|--------|
| Model Preloading | High | 1 day | High | Planned |
| Connection Pooling | Medium | 2 days | Medium | Planned |
| WebSocket Streaming | Medium | 2-3 weeks | High | Planned |
| Python Client SDK | Medium | 1 week | Medium | Planned |
| GPU Batching | Medium | 1-2 weeks | Medium | Research |
| Multi-Model Support | Low | 2 weeks | Low | Planned |
| Speaker Diarization | Low | 3-4 weeks | Low | Research |

---

## Feedback & Suggestions

Have ideas for new features? Open an issue on GitHub or start a discussion:
- [GitHub Issues](https://github.com/2oby/ORAC-STT/issues)
- [GitHub Discussions](https://github.com/2oby/ORAC-STT/discussions)

---

**Last Updated:** October 17, 2025
**Version:** 0.2.0
**Maintained by:** ORAC Team
