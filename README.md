# ORAC STT Service

The ORAC STT (Speech-to-Text) Service is designed to run on NVIDIA Orin Nano, providing fast, robust, and secure speech-to-text conversion for the ORAC system. It receives audio streams from the Hey ORAC wake word service and transcribes them using **whisper.cpp** - a high-performance C++ implementation of OpenAI's Whisper with native CUDA acceleration optimized for Jetson/Orin hardware.

## Key Features

- **HTTP API**: Accepts POST requests at `/stt/v1/stream` for 16kHz 16-bit mono WAV/PCM audio. Supports model selection via `X-Model-Name` header and optional Bearer token authentication.
- **gRPC Stub**: Includes a bidirectional gRPC endpoint (disabled by default) with protobuf schema for future streaming support.
- **Model Management**: Uses whisper.cpp with GGML quantized models (tiny/base/small available) optimized for edge deployment. Built specifically for Orin Nano with CUDA compute capability 8.7.
- **Egress to Command API**: Posts transcribed text, confidence, and language to the Command API, with robust error handling and exponential backoff retries.
- **Performance**: Targets <500ms median latency from speech end to text, and <25% sustained CPU usage on Orin Nano 8GB.
- **Security**: Implements mutual TLS (mTLS) with self-signed certificates and a 6-digit PIN pairing process for secure first-run setup.
- **Observability**: Provides Prometheus `/metrics` and `/health` endpoints for monitoring, and includes circuit breaker logic for repeated decode errors.
- **Deployment**: Fully containerized (~500MB vs 3-4GB PyTorch), with whisper.cpp binaries and GGML models mounted as volumes for efficient updates.

## Technical Highlights

- **Audio Format**: 16kHz, 16-bit mono WAV (FLAC support planned)
- **API Response**: Responds 202 Accepted immediately, streams decoded text when ready
- **Robustness**: Auto-restarts on GPU/driver failure
- **Future Hooks**: Reserved fields for speaker ID and word-level timestamps in protobuf; planned streaming partial ASR via gRPC

## Configuration

The service uses a configuration file system with environment variable overrides:

1. **Copy the template**: `cp config.toml.example config.toml`
2. **Edit your settings**: Modify `config.toml` for your environment
3. **Override with env vars**: Use `ORAC_` prefix (e.g., `ORAC_LOG_LEVEL=DEBUG`)

### Configuration Sections:
- **App settings**: Logging, environment mode
- **Model**: Whisper model selection, GPU/CPU device, cache directory
- **API**: Host, port, timeouts, audio duration limits
- **Command API**: Downstream service integration
- **Security**: TLS/mTLS certificates and settings

## Getting Started

### Quick Deploy to Orin Nano
```bash
# Deploy and test
cd scripts
./deploy_and_test.sh

# Check logs
ssh orin3 "docker logs -f orac-stt"

# Test endpoints
curl http://orin3:8000/health
curl http://orin3:8000/metrics
```

### Development
1. Copy and customize configuration: `cp config.toml.example config.toml`
2. Build and deploy the service using Docker Compose or systemd
3. Send audio to `/stt/v1/stream` and receive transcriptions
4. Monitor health and metrics endpoints for observability

## whisper.cpp for Orin Nano

This project uses **whisper.cpp** instead of PyTorch for better performance on Jetson/Orin hardware. The implementation provides:

- **Native CUDA Support**: Compiled with cuBLAS for GPU acceleration
- **Smaller Footprint**: ~500MB container vs 3-4GB PyTorch images  
- **GGML Models**: Quantized models are 4-8x smaller than PyTorch equivalents
- **Orin Optimized**: Built for CUDA compute capability 8.7

### Building whisper.cpp on Orin

The whisper.cpp binaries are built directly on the Orin Nano during first deployment:

```bash
# Automatic build during deployment
cd scripts && ./deploy_and_test.sh

# Manual build (if needed)
ssh orin3
cd /home/toby/orac-stt/third_party/whisper_cpp
./build_whisper_cpp.sh
```

The build script:
1. **Installs dependencies**: cmake, build-essential, git
2. **Clones whisper.cpp**: Latest version from GitHub
3. **Compiles with CUDA**: Uses cuBLAS for GPU acceleration
4. **Creates binaries**: whisper-cli, quantize, whisper-server, etc.
5. **Downloads models**: GGML format (tiny, base, small)

**Build time**: ~10-15 minutes (one-time setup)  
**Requirements**: 8GB+ swap, sudo access for dependencies

### Available Models

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny  | 39MB | Fastest | Basic | Real-time, low latency |
| base  | 147MB | Balanced | Good | General purpose (default) |
| small | 244MB | Slower | Better | Higher accuracy needed |

### Container Architecture

```
NVIDIA CUDA 12.6 Runtime Container (~500MB)
├── FastAPI Application (Python)
├── whisper.cpp binaries (mounted from host)
├── GGML models (mounted from host)  
└── GPU acceleration via cuBLAS
```

For detailed setup, deployment, and API usage, see the `CURRENT_FOCUS.md` file.
