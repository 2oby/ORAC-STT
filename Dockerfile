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
    git \
    libsndfile1 \
    ffmpeg \
    build-essential \
    cmake \
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
    python-multipart==0.0.6 \
    PyYAML==6.0.1

# Install Python dependencies - Audio Processing
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    scipy==1.11.4 \
    librosa==0.10.1 \
    soundfile==0.12.1

# Install HTTP client for ORAC Core integration
RUN pip install --no-cache-dir \
    aiohttp==3.9.1

# Build whisper.cpp with CUDA support
RUN cd /tmp && \
    git clone https://github.com/ggerganov/whisper.cpp && \
    cd whisper.cpp && \
    # Build with CUDA support for Jetson
    CUDACXX=/usr/local/cuda/bin/nvcc make -j$(nproc) GGML_CUDA=1 && \
    # Build the shared library
    make libwhisper.so && \
    # Copy binaries and library
    mkdir -p /app/third_party/whisper_cpp/bin && \
    cp main /app/third_party/whisper_cpp/bin/whisper-cli && \
    cp libwhisper.so /usr/local/lib/ && \
    ldconfig && \
    # Clean up
    cd / && rm -rf /tmp/whisper.cpp

# Copy application code
COPY src/ ./src/
COPY config.toml.example ./config.toml

# Create necessary directories
RUN mkdir -p /app/models /app/logs /app/certs

# Expose port
EXPOSE 7272

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7272/health || exit 1

# Run the application
CMD ["python", "-m", "src.orac_stt.main"]