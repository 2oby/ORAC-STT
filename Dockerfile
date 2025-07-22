# Minimal Dockerfile for ORAC STT Service
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (only core ones for now)
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    pydantic-settings==2.1.0 \
    prometheus-client==0.19.0 \
    toml==0.10.2 \
    tomli==2.0.1

# Copy application code
COPY src/ ./src/
COPY config.toml.example ./config.toml

# Create necessary directories
RUN mkdir -p /app/models /app/logs /app/certs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "src.orac_stt.main"]