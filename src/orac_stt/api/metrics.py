"""Prometheus metrics endpoint."""

from typing import Dict, Any
import time

from fastapi import APIRouter, Response
from prometheus_client import (
    Counter, Histogram, Gauge, 
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry
)

from ..utils.logging import get_logger

logger = get_logger(__name__)

# Create a custom registry to avoid conflicts
registry = CollectorRegistry()

# Define metrics
request_count = Counter(
    'orac_stt_requests_total',
    'Total number of STT requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

request_duration = Histogram(
    'orac_stt_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    registry=registry
)

active_requests = Gauge(
    'orac_stt_active_requests',
    'Number of active requests',
    registry=registry
)

stt_processing_duration = Histogram(
    'orac_stt_processing_duration_seconds',
    'STT processing duration in seconds',
    ['model'],
    registry=registry
)

model_load_time = Gauge(
    'orac_stt_model_load_time_seconds',
    'Time taken to load the model',
    ['model'],
    registry=registry
)

audio_duration = Histogram(
    'orac_stt_audio_duration_seconds',
    'Duration of processed audio in seconds',
    registry=registry
)

error_count = Counter(
    'orac_stt_errors_total',
    'Total number of errors',
    ['error_type'],
    registry=registry
)

# GPU metrics placeholders
gpu_utilization = Gauge(
    'orac_stt_gpu_utilization_percent',
    'GPU utilization percentage',
    registry=registry
)

gpu_memory_used = Gauge(
    'orac_stt_gpu_memory_used_bytes',
    'GPU memory used in bytes',
    registry=registry
)

# Create router
router = APIRouter()


@router.get(
    "/metrics",
    response_class=Response,
    summary="Prometheus metrics",
    description="Expose metrics in Prometheus format"
)
async def metrics():
    """Return metrics in Prometheus format."""
    # TODO: Update GPU metrics when GPU monitoring is implemented
    # For now, set some default values
    gpu_utilization.set(0)
    gpu_memory_used.set(0)
    
    # Generate metrics output
    metrics_output = generate_latest(registry)
    
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST
    )


class MetricsMiddleware:
    """Middleware to collect request metrics."""
    
    def __init__(self):
        self.start_time = None
        
    async def __call__(self, request, call_next):
        """Process request and collect metrics."""
        # Record active request
        active_requests.inc()
        
        # Start timing
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            request_count.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            
            return response
            
        except Exception as e:
            # Record error
            error_count.labels(error_type=type(e).__name__).inc()
            raise
            
        finally:
            # Decrement active requests
            active_requests.dec()