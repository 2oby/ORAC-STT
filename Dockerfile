# ORAC STT Service Dockerfile with GPU Support
FROM nvidia/cuda:12.6.0-runtime-ubuntu22.04

# Set environment variables for GPU
ENV CUDA_VISIBLE_DEVICES=0
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies and Python
RUN apt-get update && apt-get install -y \
    python3.10 python3.10-dev python3-pip \
    curl \
    libsndfile1 \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies - Core
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    pydantic-settings==2.1.0 \
    prometheus-client==0.19.0 \
    toml==0.10.2 \
    tomli==2.0.1 \
    python-multipart==0.0.6

# Install Python dependencies - Audio Processing
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    scipy==1.11.4 \
    librosa==0.10.1 \
    soundfile==0.12.1

# We'll use whisper.cpp instead of PyTorch for better performance on Jetson
# The whisper.cpp binaries will be built on the device and copied in

# Copy application code
COPY src/ ./src/
COPY config.toml.example ./config.toml

# Create necessary directories
RUN mkdir -p /app/models /app/logs /app/certs /app/third_party/whisper_cpp/bin

# Note: whisper.cpp binaries should be built on Jetson and mounted at runtime
# via: -v /path/to/whisper_cpp/bin:/app/third_party/whisper_cpp/bin

# Expose port
EXPOSE 7272

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7272/health || exit 1

# Run the application
CMD ["python", "-m", "src.orac_stt.main"]