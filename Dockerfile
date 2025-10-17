# ORAC STT Service Dockerfile with GPU Support
FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04

# Set environment variables
ENV CUDA_VISIBLE_DEVICES=0
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:${PATH}"
# Set library path for whisper.cpp (will be mounted at runtime)
ENV LD_LIBRARY_PATH="/app/third_party/whisper_cpp/lib:${LD_LIBRARY_PATH}"

# Set working directory
WORKDIR /app

# Install system dependencies and Python
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    curl \
    libsndfile1 \
    ffmpeg \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Ensure pip is up to date
RUN python3.10 -m pip install --upgrade pip setuptools wheel

# Install production dependencies only
# - requirements.txt: Core dependencies (FastAPI, audio processing, etc.)
# - requirements-dev.txt: NOT installed in production (keeps image small)
# - requirements-pytorch.txt: NOT installed (we use whisper.cpp, not PyTorch)
COPY requirements.txt .
RUN python3.10 -m pip install --no-cache-dir -r requirements.txt

# Optional: Install PyTorch backend (if needed for testing)
# Uncomment the following lines to install PyTorch support:
# COPY requirements-pytorch.txt .
# RUN python3.10 -m pip install --no-cache-dir -r requirements-pytorch.txt

# Verify critical packages are installed
RUN python3.10 -c "import uvicorn; print('uvicorn installed:', uvicorn.__version__)"
RUN python3.10 -c "import fastapi; print('fastapi installed:', fastapi.__version__)"
RUN python3.10 -c "import pydantic; print('pydantic installed:', pydantic.__version__)"

# Note: PyTorch dependencies (requirements-pytorch.txt) are NOT installed by default.
# whisper.cpp is used instead for better performance on Jetson devices.

# Copy application code
COPY src/ ./src/
COPY config.toml.example ./config.toml

# Create necessary directories
RUN mkdir -p /app/models /app/logs /app/certs /app/third_party/whisper_cpp

# Expose port
EXPOSE 7272

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7272/health || exit 1

# Use python3.10 explicitly in CMD for consistency
CMD ["/usr/bin/python3.10", "-m", "src.orac_stt.main"]