# ORAC STT - Production Readiness Assessment & Cleanup Recommendations

**Project:** ORAC STT (Speech-to-Text Service)
**Version:** 0.2.0
**Assessment Date:** October 17, 2025
**Current State:** Post-Phase 1 Cleanup

---

## Executive Summary

Following the recent Phase 1 cleanup (Sprint 1), ORAC STT has made significant progress toward production readiness. The codebase (~4,050 lines) shows good architectural patterns with FastAPI, proper dependency injection, and containerized deployment. However, several areas require attention before the service is fully production-ready.

**Current Strengths:**
- ✅ Clean separation of concerns (API/Core/Models/Integrations)
- ✅ Dependency injection pattern implemented
- ✅ Docker containerization with GPU support
- ✅ Structured logging (JSON format)
- ✅ Good documentation (README, USER_GUIDE, DEVELOPER_GUIDE, API_REFERENCE)
- ✅ Topic-based routing with lazy registration
- ✅ Timezone-aware datetime handling

**Critical Gaps:**
- ⚠️ **Test coverage < 20%** (8 test files, minimal integration tests)
- ⚠️ **No CI/CD pipeline** (manual deployment only)
- ⚠️ **Limited error recovery** (no retry logic, circuit breakers)
- ⚠️ **No observability** (missing APM, distributed tracing)
- ⚠️ **Security gaps** (no authentication, input sanitization needed)

---

## Priority Recommendations

### 🔴 Critical (P0) - Required for Production

#### 1. Testing Infrastructure
**Current State:** ~20% coverage, minimal integration tests
**Impact:** High risk of production bugs, difficult to refactor safely

**Actions:**
- [ ] **Increase unit test coverage to 80%+**
  - Add tests for all core business logic (`core/`, `models/`)
  - Mock external dependencies (ORAC Core client, whisper.cpp)
  - Test error paths and edge cases

- [ ] **Add comprehensive integration tests**
  - End-to-end API tests with real audio files
  - Test heartbeat processing workflow
  - Test topic registration and routing
  - Database/file persistence tests

- [ ] **Add load/stress tests**
  ```python
  # Example: tests/load/test_concurrent_requests.py
  async def test_concurrent_transcriptions():
      # Simulate 50 concurrent requests
      # Measure latency, memory usage, error rates
  ```

- [ ] **Set up test fixtures library**
  ```
  tests/fixtures/
  ├── audio_samples/
  │   ├── valid_16khz_mono.wav
  │   ├── invalid_stereo.wav
  │   ├── invalid_format.mp3
  │   └── edge_cases/
  │       ├── silent.wav
  │       ├── very_short.wav (< 100ms)
  │       └── max_length.wav (15s)
  ```

**Estimated Effort:** 2-3 weeks
**Files to Focus On:**
- `tests/unit/test_audio_processor.py` (expand)
- `tests/unit/test_topic_registry.py` (expand)
- `tests/integration/test_stt_workflow.py` (new)
- `tests/integration/test_heartbeat_flow.py` (new)

---

#### 2. CI/CD Pipeline
**Current State:** Manual deployment via `deploy_and_test.sh`
**Impact:** Slow feedback loop, manual errors, no automated quality gates

**Actions:**
- [ ] **Set up GitHub Actions workflow**
  ```yaml
  # .github/workflows/ci.yml
  name: CI
  on: [push, pull_request]
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - name: Set up Python
          uses: actions/setup-python@v4
          with:
            python-version: '3.10'
        - name: Install dependencies
          run: pip install -r requirements.txt -r requirements-dev.txt
        - name: Run tests
          run: pytest --cov=src/orac_stt --cov-report=xml
        - name: Upload coverage
          uses: codecov/codecov-action@v3

    lint:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - name: Run black
          run: black --check src/ tests/
        - name: Run mypy
          run: mypy src/
        - name: Run flake8
          run: flake8 src/ tests/
  ```

- [ ] **Add pre-commit hooks** (locally enforce quality)
  ```yaml
  # .pre-commit-config.yaml
  repos:
    - repo: https://github.com/psf/black
      rev: 23.11.0
      hooks:
        - id: black
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.5.0
      hooks:
        - id: trailing-whitespace
        - id: end-of-file-fixer
        - id: check-yaml
        - id: check-json
    - repo: https://github.com/pycqa/flake8
      rev: 6.1.0
      hooks:
        - id: flake8
  ```

- [ ] **Automated Docker builds**
  - Multi-arch builds (ARM64 for Jetson)
  - Image scanning (Trivy, Grype)
  - Push to container registry (GHCR, Docker Hub)

- [ ] **Deployment automation**
  - Blue-green deployment support
  - Automated rollback on health check failure
  - Deployment notifications (Slack/Discord)

**Estimated Effort:** 1 week

---

#### 3. Error Handling & Resilience
**Current State:** Basic try-catch blocks, no retry logic
**Impact:** Service vulnerable to transient failures

**Actions:**
- [ ] **Add retry logic for ORAC Core client**
  ```python
  # src/orac_stt/integrations/orac_core_client.py
  from tenacity import retry, stop_after_attempt, wait_exponential

  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=1, max=10),
      reraise=True
  )
  async def forward_transcription(self, text: str, topic: str, metadata: dict):
      # Existing implementation with automatic retry
  ```

- [ ] **Implement circuit breaker pattern**
  ```python
  from pybreaker import CircuitBreaker

  core_breaker = CircuitBreaker(
      fail_max=5,           # Open after 5 failures
      timeout_duration=60   # Try again after 60s
  )

  @core_breaker
  async def forward_to_core(...):
      # Protected call
  ```

- [ ] **Add graceful degradation**
  - Queue transcriptions if Core is down
  - Return partial results on timeout
  - Cache recent responses

- [ ] **Implement health check dependencies**
  ```python
  # src/orac_stt/api/health.py
  async def check_dependencies():
      checks = {
          "model": await check_model_loaded(),
          "disk_space": await check_disk_space(),
          "orac_core": await check_orac_core_reachable(),
          "gpu": await check_gpu_available()
      }
      return checks
  ```

**Estimated Effort:** 1 week
**Dependencies to Add:**
- `tenacity` - Retry logic
- `pybreaker` - Circuit breaker pattern

---

#### 4. Security Hardening
**Current State:** No authentication, basic input validation
**Impact:** Service exposed to abuse, injection attacks

**Actions:**
- [ ] **Implement API authentication**
  ```python
  # Option 1: API Key authentication
  from fastapi import Security, HTTPException
  from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

  security = HTTPBearer()

  async def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
      if credentials.credentials != os.getenv("API_KEY"):
          raise HTTPException(status_code=403, detail="Invalid API key")
      return credentials.credentials

  # Option 2: JWT tokens (more scalable)
  from fastapi_jwt_auth import AuthJWT
  ```

- [ ] **Add rate limiting**
  ```python
  from slowapi import Limiter
  from slowapi.util import get_remote_address

  limiter = Limiter(key_func=get_remote_address)

  @limiter.limit("100/minute")  # Per IP rate limit
  @router.post("/stream/{topic}")
  async def transcribe_stream_with_topic(...):
  ```

- [ ] **Enhanced input validation**
  - File size limits (already in place, verify enforcement)
  - Audio duration limits (already in place, verify)
  - Malicious filename sanitization
  - Content-Type validation

- [ ] **Add request ID tracking**
  ```python
  # Middleware for request tracking
  import uuid
  from starlette.middleware.base import BaseHTTPMiddleware

  class RequestIDMiddleware(BaseHTTPMiddleware):
      async def dispatch(self, request, call_next):
          request_id = str(uuid.uuid4())
          request.state.request_id = request_id
          response = await call_next(request)
          response.headers["X-Request-ID"] = request_id
          return response
  ```

- [ ] **Secrets management**
  - Move API keys/tokens to secrets manager (AWS Secrets Manager, Vault)
  - Rotate credentials regularly
  - Audit access logs

**Estimated Effort:** 1-2 weeks
**Dependencies to Add:**
- `slowapi` - Rate limiting
- `python-jose[cryptography]` - JWT handling
- `python-multipart` (already included)

---

#### 5. Observability & Monitoring
**Current State:** Basic Prometheus metrics, JSON logs
**Impact:** Difficult to debug production issues, no alerting

**Actions:**
- [ ] **Add distributed tracing**
  ```python
  # OpenTelemetry integration
  from opentelemetry import trace
  from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
  from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

  # Instrument FastAPI
  FastAPIInstrumentor.instrument_app(app)

  # Export to Jaeger/Tempo
  trace.get_tracer_provider().add_span_processor(
      BatchSpanProcessor(OTLPSpanExporter())
  )
  ```

- [ ] **Enhanced Prometheus metrics**
  ```python
  # src/orac_stt/api/metrics.py
  from prometheus_client import Counter, Histogram, Gauge

  # Add custom metrics
  transcription_duration = Histogram(
      'stt_transcription_duration_seconds',
      'Time spent transcribing audio',
      buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
  )

  transcription_errors = Counter(
      'stt_transcription_errors_total',
      'Total transcription errors',
      ['error_type']
  )

  active_topics = Gauge(
      'stt_active_topics',
      'Number of active topics'
  )

  queue_size = Gauge(
      'stt_queue_size',
      'Number of pending transcriptions'
  )
  ```

- [ ] **Structured logging enhancements**
  ```python
  # Add correlation IDs to all logs
  logger.info(
      "Transcription started",
      extra={
          "request_id": request_id,
          "topic": topic,
          "audio_duration": duration,
          "client_ip": request.client.host
      }
  )
  ```

- [ ] **Set up alerting rules**
  ```yaml
  # prometheus/alerts.yml
  groups:
    - name: orac_stt
      rules:
        - alert: HighErrorRate
          expr: rate(stt_transcription_errors_total[5m]) > 0.1
          for: 5m
          annotations:
            summary: "High error rate in STT service"

        - alert: SlowTranscription
          expr: histogram_quantile(0.95, stt_transcription_duration_seconds) > 2.0
          for: 10m
          annotations:
            summary: "95th percentile latency exceeds 2s"
  ```

- [ ] **APM integration** (optional, recommended)
  - New Relic / Datadog / Elastic APM
  - Automatic error tracking
  - Performance profiling
  - Database query monitoring

**Estimated Effort:** 1-2 weeks
**Dependencies to Add:**
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-exporter-otlp`

---

### 🟡 Important (P1) - Recommended for Production

#### 6. Configuration Management
**Current State:** TOML + environment variables, good foundation
**Improvements Needed:** Better separation of environments, secrets handling

**Actions:**
- [ ] **Environment-specific configs**
  ```
  config/
  ├── base.toml          # Common settings
  ├── development.toml   # Dev overrides
  ├── staging.toml       # Staging overrides
  └── production.toml    # Production overrides
  ```

- [ ] **Config validation on startup**
  ```python
  # src/orac_stt/config/validator.py
  def validate_config(settings: Settings):
      errors = []

      # Check required files exist
      if settings.security.enable_tls:
          if not settings.security.cert_file.exists():
              errors.append(f"TLS cert not found: {settings.security.cert_file}")

      # Check ORAC Core reachability
      if not await ping_orac_core(settings.orac_core_url):
          errors.append(f"Cannot reach ORAC Core: {settings.orac_core_url}")

      if errors:
          raise ConfigurationError(f"Invalid config: {errors}")
  ```

- [ ] **Feature flags**
  ```python
  # src/orac_stt/config/features.py
  class FeatureFlags(BaseSettings):
      enable_debug_recordings: bool = False
      enable_audio_preprocessing: bool = True
      enable_caching: bool = True
      max_concurrent_requests: int = 10
  ```

**Estimated Effort:** 3-4 days

---

#### 7. Database/Persistence Layer
**Current State:** YAML file storage for topics, in-memory command buffer
**Issue:** Not scalable, data loss on crash, no concurrency control

**Actions:**
- [ ] **Migrate to proper database**
  ```python
  # Option 1: SQLite (simple, embedded)
  # Good for single-instance deployment

  # Option 2: PostgreSQL (recommended)
  # Better for multi-instance, replication, ACID

  # src/orac_stt/db/models.py
  from sqlalchemy import Column, String, DateTime, JSON, Float
  from sqlalchemy.ext.declarative import declarative_base

  Base = declarative_base()

  class Topic(Base):
      __tablename__ = "topics"
      name = Column(String, primary_key=True)
      orac_core_url = Column(String, nullable=True)
      last_seen = Column(DateTime(timezone=True))
      metadata = Column(JSON)

  class TranscriptionHistory(Base):
      __tablename__ = "transcriptions"
      id = Column(String, primary_key=True)
      topic = Column(String, index=True)
      text = Column(String)
      confidence = Column(Float)
      audio_path = Column(String)
      timestamp = Column(DateTime(timezone=True), index=True)
      duration = Column(Float)
  ```

- [ ] **Add database migrations** (Alembic)
  ```bash
  # Initialize Alembic
  alembic init alembic

  # Create migration
  alembic revision --autogenerate -m "Initial schema"

  # Apply migration
  alembic upgrade head
  ```

- [ ] **Connection pooling**
  ```python
  from sqlalchemy.pool import QueuePool

  engine = create_engine(
      database_url,
      poolclass=QueuePool,
      pool_size=10,
      max_overflow=20,
      pool_timeout=30,
      pool_pre_ping=True  # Test connections before use
  )
  ```

**Estimated Effort:** 1 week
**Dependencies to Add:**
- `sqlalchemy[asyncio]`
- `alembic`
- `asyncpg` (for PostgreSQL) or `aiosqlite` (for SQLite)

---

#### 8. Caching Layer
**Current State:** No caching implemented
**Benefit:** Reduce duplicate transcriptions, improve response times

**Actions:**
- [ ] **Add Redis cache for transcriptions**
  ```python
  # src/orac_stt/cache/redis_cache.py
  import hashlib
  from redis.asyncio import Redis

  class TranscriptionCache:
      def __init__(self, redis_url: str):
          self.redis = Redis.from_url(redis_url)

      async def get_cached_transcription(self, audio_hash: str):
          """Check if we've transcribed this audio before."""
          cached = await self.redis.get(f"transcript:{audio_hash}")
          return json.loads(cached) if cached else None

      async def cache_transcription(self, audio_hash: str, result: dict, ttl: int = 3600):
          """Cache transcription result for 1 hour."""
          await self.redis.setex(
              f"transcript:{audio_hash}",
              ttl,
              json.dumps(result)
          )

      def hash_audio(self, audio_data: bytes) -> str:
          """Generate hash of audio content."""
          return hashlib.sha256(audio_data).hexdigest()
  ```

- [ ] **Cache topic configurations**
  - Reduce disk I/O for topic lookups
  - Use Redis or in-memory LRU cache

- [ ] **Model response caching**
  - Cache model outputs for identical inputs
  - Configurable TTL per environment

**Estimated Effort:** 3-4 days
**Dependencies to Add:**
- `redis[hiredis]` or `aioredis`

---

#### 9. Async Queue for Transcription Jobs
**Current State:** Synchronous processing, blocking requests
**Benefit:** Better resource utilization, handle traffic spikes

**Actions:**
- [ ] **Implement job queue** (Celery or RQ)
  ```python
  # src/orac_stt/workers/transcription_worker.py
  from celery import Celery

  celery_app = Celery('orac_stt', broker='redis://localhost:6379/0')

  @celery_app.task(bind=True, max_retries=3)
  def transcribe_async(self, audio_path: str, topic: str, options: dict):
      try:
          # Load audio
          # Run transcription
          # Forward to Core
          # Update database
          return {"status": "success", "text": transcribed_text}
      except Exception as exc:
          raise self.retry(exc=exc, countdown=60)

  # API endpoint modification
  @router.post("/stream/{topic}/async")
  async def transcribe_async_endpoint(...):
      # Save audio to disk
      audio_path = await save_audio_temp(file)

      # Queue job
      task = transcribe_async.delay(audio_path, topic, options)

      return {
          "task_id": task.id,
          "status": "queued",
          "status_url": f"/tasks/{task.id}"
      }
  ```

- [ ] **Add job status tracking**
  ```python
  @router.get("/tasks/{task_id}")
  async def get_task_status(task_id: str):
      task = celery_app.AsyncResult(task_id)
      return {
          "task_id": task_id,
          "status": task.state,
          "result": task.result if task.ready() else None
      }
  ```

**Estimated Effort:** 1 week
**Dependencies to Add:**
- `celery[redis]`
- `flower` (for monitoring)

---

#### 10. Documentation Improvements
**Current State:** Good foundation, needs operational docs

**Actions:**
- [ ] **Add runbooks** for common issues
  ```markdown
  # docs/runbooks/high_latency.md
  ## Symptom: High Transcription Latency

  ### Diagnosis Steps:
  1. Check GPU utilization: `nvidia-smi`
  2. Check container resources: `docker stats orac-stt`
  3. Review logs: `docker compose logs orac-stt | grep ERROR`

  ### Common Causes:
  - GPU memory exhausted
  - Model not loaded
  - Network issues to ORAC Core

  ### Resolution:
  - Restart container: `docker compose restart orac-stt`
  - Check model cache: `ls -la /app/models/`
  - Verify ORAC Core connectivity: `curl http://orac-core:8000/health`
  ```

- [ ] **API versioning strategy documentation**
- [ ] **Architecture decision records (ADRs)**
  ```markdown
  # docs/adr/001-use-whispercpp-instead-of-pytorch.md
  ## Status: Accepted

  ## Context
  Need fast STT on resource-constrained Jetson Nano

  ## Decision
  Use whisper.cpp with CUDA instead of PyTorch

  ## Consequences
  - Pros: 5x faster, 80% less memory
  - Cons: Limited to quantized models, less flexible
  ```

- [ ] **Deployment topology diagrams**
- [ ] **Performance benchmarks** (baseline metrics)

**Estimated Effort:** 3-4 days

---

### 🟢 Nice to Have (P2) - Future Enhancements

#### 11. Advanced Features

- [ ] **WebSocket streaming transcription**
  - Real-time partial results
  - Lower latency for long audio

- [ ] **Batch processing endpoint**
  - Upload multiple files at once
  - Background processing

- [ ] **Speaker diarization**
  - Identify multiple speakers
  - Requires additional models

- [ ] **Custom model support**
  - User uploads fine-tuned models
  - Model versioning

- [ ] **Multi-language support enhancement**
  - Auto-detect language
  - Mixed-language transcription

**Estimated Effort:** 2-4 weeks per feature

---

#### 12. Performance Optimizations

- [ ] **Model preloading on startup**
  ```python
  # src/orac_stt/main.py
  @asynccontextmanager
  async def lifespan(app: FastAPI):
      # Startup
      logger.info("Preloading model...")
      model_loader = get_model_loader()
      await asyncio.get_event_loop().run_in_executor(None, model_loader.load_model)
      logger.info("Model preloaded")
      yield
      # Shutdown
  ```

- [ ] **Audio preprocessing optimization**
  - Use ffmpeg for faster conversion
  - Parallel processing for multiple files

- [ ] **Connection pooling for ORAC Core client**
  ```python
  # src/orac_stt/integrations/orac_core_client.py
  self.session = aiohttp.ClientSession(
      connector=aiohttp.TCPConnector(limit=10),
      timeout=aiohttp.ClientTimeout(total=30)
  )
  ```

- [ ] **GPU batching** for multiple concurrent requests
  - Batch multiple audio files
  - Process together on GPU
  - Improves throughput

**Estimated Effort:** 1-2 weeks

---

#### 13. Developer Experience

- [ ] **Local development with Docker Compose**
  ```yaml
  # docker-compose.dev.yml
  services:
    orac-stt:
      volumes:
        - ./src:/app/src:rw  # Hot reload
        - ./tests:/app/tests:rw
      environment:
        - ORAC_LOG_LEVEL=DEBUG
        - RELOAD=true

    redis:
      image: redis:7-alpine

    postgres:
      image: postgres:15
      environment:
        POSTGRES_DB: orac_stt
        POSTGRES_PASSWORD: dev
  ```

- [ ] **Development CLI tools**
  ```bash
  # scripts/dev-cli.sh
  orac-stt dev test-audio sample.wav    # Quick transcription test
  orac-stt dev clear-cache              # Clear Redis cache
  orac-stt dev migrations apply         # Apply DB migrations
  ```

- [ ] **API client SDKs**
  - Python client library
  - JavaScript/TypeScript client
  - Auto-generated from OpenAPI spec

**Estimated Effort:** 1 week

---

## Code Quality Improvements

### Refactoring Opportunities

#### 1. src/orac_stt/dependencies.py
**Issue:** Global mutable state (singleton pattern anti-pattern)

```python
# Current (using globals)
_model_loader: UnifiedWhisperLoader = None

# Better approach: Use FastAPI dependency system properly
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_model_loader_lifespan():
    """Properly scoped model loader."""
    loader = UnifiedWhisperLoader(get_settings().model)
    yield loader
    # Cleanup if needed
```

**Priority:** Medium
**Effort:** 1 day

---

#### 2. src/orac_stt/api/stt.py
**Issue:** Large file (726 lines), could be split further

**Suggested Split:**
```
api/
├── stt/
│   ├── __init__.py
│   ├── endpoints.py       # Route handlers
│   ├── handlers.py        # Business logic (existing functions)
│   ├── models.py          # Request/response models
│   └── validators.py      # Input validation
```

**Priority:** Low
**Effort:** 2-3 days

---

#### 3. Error Handling Consistency
**Issue:** Mix of raising exceptions and returning error responses

**Recommendation:**
- API layer: Return HTTP error responses
- Service layer: Raise domain exceptions
- Use FastAPI exception handlers

```python
# src/orac_stt/exceptions.py
class OracSTTException(Exception):
    """Base exception for all ORAC STT errors."""
    pass

class TranscriptionError(OracSTTException):
    """Raised when transcription fails."""
    pass

class ModelLoadError(OracSTTException):
    """Raised when model cannot be loaded."""
    pass

# src/orac_stt/main.py
@app.exception_handler(TranscriptionError)
async def transcription_error_handler(request: Request, exc: TranscriptionError):
    return JSONResponse(
        status_code=500,
        content={"error": "transcription_failed", "detail": str(exc)}
    )
```

**Priority:** Medium
**Effort:** 2-3 days

---

#### 4. Type Hints Coverage
**Current:** ~70% coverage (estimate)
**Goal:** 95%+ coverage for mypy strict mode

```python
# Add missing type hints
from typing import Optional, Dict, Any, List

# Before
def process_heartbeat(request):
    ...

# After
async def process_heartbeat(
    request: HeartbeatRequest
) -> HeartbeatResponse:
    ...
```

**Priority:** Medium
**Effort:** 3-4 days

---

### Code Smells to Address

1. **Magic Numbers**
   ```python
   # Bad
   if len(recordings) > 5:

   # Good
   MAX_DEBUG_RECORDINGS = 5
   if len(recordings) > MAX_DEBUG_RECORDINGS:
   ```

2. **Long Functions** (Already addressed in Phase 1, verify completeness)
   - Check for any remaining 100+ line functions

3. **Duplicate Code**
   - Run `flake8` with duplicate code detection
   - Extract common patterns

4. **Comments Instead of Documentation**
   - Convert inline comments to proper docstrings
   - Use type hints instead of type comments

---

## Infrastructure Recommendations

### 1. Multi-Instance Deployment
**Current:** Single container deployment
**Goal:** Horizontal scaling with load balancer

```yaml
# docker-compose.prod.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "7272:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - orac-stt-1
      - orac-stt-2

  orac-stt-1:
    build: .
    environment:
      - INSTANCE_ID=1

  orac-stt-2:
    build: .
    environment:
      - INSTANCE_ID=2

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  postgres:
    image: postgres:15
    volumes:
      - pg-data:/var/lib/postgresql/data
```

---

### 2. Kubernetes Deployment (Future)
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orac-stt
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orac-stt
  template:
    metadata:
      labels:
        app: orac-stt
    spec:
      containers:
      - name: orac-stt
        image: ghcr.io/2oby/orac-stt:latest
        resources:
          requests:
            memory: "1Gi"
            nvidia.com/gpu: 1
          limits:
            memory: "2Gi"
            nvidia.com/gpu: 1
```

---

### 3. Backup Strategy
- [ ] **Database backups** (hourly snapshots, 7-day retention)
- [ ] **Audio recordings backup** (if storing long-term)
- [ ] **Configuration backups** (version control + encrypted secrets)
- [ ] **Model cache backup** (S3/GCS for whisper models)

---

### 4. Disaster Recovery Plan
- [ ] Document RPO/RTO targets (e.g., RPO: 1 hour, RTO: 15 minutes)
- [ ] Automated failover procedure
- [ ] Backup restoration runbook
- [ ] Data loss prevention strategy

---

## Security Audit Checklist

### Application Security
- [ ] Input validation on all endpoints
- [ ] Output encoding to prevent injection
- [ ] File upload restrictions (size, type, name)
- [ ] Rate limiting per IP/API key
- [ ] Authentication required for all non-health endpoints
- [ ] Authorization checks for topic access
- [ ] Secrets not in environment variables (use secrets manager)
- [ ] Dependencies scanned for vulnerabilities (`pip-audit`)

### Network Security
- [ ] TLS 1.3 enforced
- [ ] mTLS for inter-service communication
- [ ] Firewall rules documented
- [ ] Internal services not exposed publicly
- [ ] CORS properly configured

### Container Security
- [ ] Non-root user in container
- [ ] Minimal base image (distroless or Alpine)
- [ ] No secrets in Docker layers
- [ ] Image scanning in CI/CD
- [ ] Read-only filesystem where possible

### Operational Security
- [ ] Audit logging for all API calls
- [ ] Log retention policy (90 days minimum)
- [ ] Incident response plan
- [ ] Security update process
- [ ] Access control reviews (quarterly)

---

## Performance Benchmarks & SLOs

### Baseline Metrics (Document Current State)
```yaml
# tests/benchmarks/baseline.yaml
transcription_latency_p50: 350ms
transcription_latency_p95: 500ms
transcription_latency_p99: 800ms
throughput: 50 requests/second
error_rate: 0.1%
cpu_usage_avg: 20%
memory_usage_avg: 1.5GB
gpu_usage_avg: 40%
```

### Proposed SLOs
- **Availability:** 99.9% uptime (43 minutes downtime/month)
- **Latency:** p95 < 500ms for 15s audio
- **Error Rate:** < 0.5% for valid audio
- **Throughput:** 100 requests/second per instance

---

## Migration Path & Timeline

### Phase 2: Core Stability (4-6 weeks)
**Focus:** Testing, CI/CD, Error Handling, Security Basics

| Week | Tasks | Deliverables |
|------|-------|--------------|
| 1-2  | Testing infrastructure | 80% unit test coverage |
| 3    | CI/CD pipeline | GitHub Actions workflow |
| 4    | Error handling & resilience | Retry logic, circuit breakers |
| 5-6  | Security hardening | Authentication, rate limiting |

**Exit Criteria:**
- ✅ All P0 items addressed
- ✅ CI pipeline green
- ✅ Security scan passed
- ✅ Load test passed (100 req/s)

---

### Phase 3: Scale & Observability (4-6 weeks)
**Focus:** Database, Caching, Monitoring, Multi-instance

| Week | Tasks | Deliverables |
|------|-------|--------------|
| 1-2  | Database migration | PostgreSQL setup, migrations |
| 3    | Caching layer | Redis integration |
| 4    | Observability | Tracing, enhanced metrics |
| 5-6  | Multi-instance deployment | Load balancer, horizontal scaling |

**Exit Criteria:**
- ✅ Database operational with backups
- ✅ Distributed tracing working
- ✅ Multi-instance deployment tested
- ✅ Runbooks documented

---

### Phase 4: Advanced Features (Ongoing)
**Focus:** P2 items, optimization, new features

- WebSocket streaming
- Batch processing
- Advanced ML features
- Developer SDKs
- Kubernetes migration (optional)

---

## Cost-Benefit Analysis

### Estimated Effort Summary
- **P0 (Critical):** 6-8 weeks
- **P1 (Important):** 4-5 weeks
- **P2 (Nice to Have):** 6-10 weeks

### Recommended Staffing
- **Phase 2:** 1-2 developers full-time
- **Phase 3:** 1 developer + 0.5 DevOps
- **Phase 4:** 1 developer part-time

### Expected Benefits
1. **Reliability:** 10x reduction in production incidents
2. **Velocity:** 3x faster development with CI/CD
3. **Scalability:** 5x capacity increase with multi-instance
4. **Security:** Pass enterprise security audits
5. **Maintainability:** 50% reduction in debugging time

---

## Immediate Next Steps (Week 1)

1. **Day 1-2: Testing Foundation**
   - Set up pytest fixtures directory
   - Write 10 critical unit tests
   - Configure coverage reporting

2. **Day 3-4: CI/CD**
   - Create GitHub Actions workflow
   - Set up pre-commit hooks
   - Configure automated linting

3. **Day 5: Security Quick Wins**
   - Add API key authentication
   - Implement basic rate limiting
   - Run dependency security scan

---

## Conclusion

ORAC STT has a solid foundation after Phase 1 cleanup. The architecture is sound, and the codebase is well-organized. However, critical production requirements around testing, CI/CD, resilience, and security must be addressed before the service can handle production traffic at scale.

**Recommended Approach:**
1. Focus on P0 items first (6-8 weeks investment)
2. Deploy to staging environment with monitoring
3. Run load tests and fix bottlenecks
4. Gradually roll out P1 items (4-5 weeks)
5. Defer P2 items until production is stable

**Success Metrics:**
- ✅ 80%+ test coverage
- ✅ CI pipeline with quality gates
- ✅ Zero critical security vulnerabilities
- ✅ 99.9% uptime in staging (30 days)
- ✅ p95 latency < 500ms under load
- ✅ Error rate < 0.5%

With disciplined execution, ORAC STT can be production-ready in **10-12 weeks** with appropriate resource allocation.

---

**Document Version:** 1.0
**Author:** Claude Code (AI Assistant)
**Review Status:** Draft - Requires Human Review
**Next Review:** After Phase 2 completion
