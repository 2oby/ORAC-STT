# ORAC STT Service

The ORAC STT (Speech-to-Text) Service is designed to run on NVIDIA Orin Nano, providing fast, robust, and secure speech-to-text conversion for the ORAC system. It receives audio streams from the Hey ORAC wake word service and transcribes them using **whisper.cpp** - a high-performance C++ implementation of OpenAI's Whisper with native CUDA acceleration optimized for Jetson/Orin hardware.

## Key Features

- **HTTP STT API**: Accepts POST requests at `/stt/v1/stream/{topic}` for 16kHz 16-bit mono WAV/PCM audio with topic-based routing. Supports model selection via `X-Model-Name` header and optional Bearer token authentication.
- **Topic System Integration**: Forwards transcriptions to ORAC Core with topic context for grammar-based generation and context-aware processing.
- **Web Admin Interface**: Real-time monitoring dashboard at `/admin/` with command history, audio playback, model management, and topic visualization.
- **Heartbeat Support**: Receives and processes heartbeats from Hey ORAC, maintaining active connection status and topic registry.
- **Model Management**: Uses whisper.cpp with GGML quantized models (tiny/base/small available) optimized for edge deployment. Built specifically for Orin Nano with CUDA compute capability 8.7.
- **ORAC Core Integration**: Automatically forwards transcribed text with topic metadata to ORAC Core for AI processing.
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

## Dependencies

The project uses split requirements files for better organization and smaller production images:

- **requirements.txt** - Core production dependencies (FastAPI, audio processing, etc.)
- **requirements-dev.txt** - Development tools (pytest, black, mypy, etc.)
- **requirements-pytorch.txt** - Optional PyTorch backend (not needed with whisper.cpp)

### Installation

**Production deployment** (Docker container):
```bash
# Automatically installed via Dockerfile - only requirements.txt
docker-compose up -d --build
```

**Local development**:
```bash
# Install production dependencies
pip install -r requirements.txt

# Install development tools
pip install -r requirements-dev.txt
```

**Optional PyTorch backend** (not needed for whisper.cpp):
```bash
pip install -r requirements-pytorch.txt
```

**Note:** The default configuration uses whisper.cpp (not PyTorch), so `requirements-pytorch.txt` is not installed in production. This keeps the Docker image at ~500MB instead of 3-4GB.

## Getting Started

### End User Quick Start

1. **Access the Web Interface**: Open `http://orac-stt-host:7272/admin/` in your browser
2. **Monitor Commands**: View real-time transcriptions as they appear
3. **Play Audio**: Click play buttons to hear recorded commands
4. **Check Status**: Verify "Dashboard Connected" status in the top bar

### Quick Deploy to Orin Nano
```bash
# Deploy and test
cd scripts
./deploy_and_test.sh

# Check logs
ssh orac-stt-host "docker logs -f orac-stt"

# Test endpoints
curl http://orac-stt-host:7272/health
curl http://orac-stt-host:7272/metrics
```

### Web Admin Interface

The admin dashboard provides real-time monitoring and management:

**URL**: `http://orac-stt-host:7272/admin/`

**Features**:
- **Real-time Command Feed**: Live transcriptions with timestamps and confidence scores
- **Audio Playback**: Play/pause controls for each recorded command
- **Connection Status**: WebSocket connection indicator ("Dashboard Connected/Disconnected")
- **Command Cards**: Grid layout showing:
  - Timestamp (HH:MM format)
  - Confidence percentage
  - Transcribed text
  - Audio duration
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Error Handling**: Visual indicators for failed transcriptions

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
ssh orac-stt-host
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

## API Reference

### STT Endpoint

**POST** `/stt/v1/stream`

Transcribes audio to text using whisper.cpp models.

**Headers**:
- `Content-Type: audio/wav` (required)
- `X-Model-Name: base` (optional, defaults to "base")
- `Authorization: Bearer <token>` (optional)

**Request Body**: 16kHz, 16-bit mono WAV audio data

**Response**: `202 Accepted` with JSON:
```json
{
  "text": "transcribed speech text",
  "confidence": 0.95,
  "language": "en",
  "duration_ms": 1450
}
```

**Example**:
```bash
# Test with audio file
curl -X POST \
  -H "Content-Type: audio/wav" \
  -H "X-Model-Name: base" \
  --data-binary @test_audio.wav \
  http://orac-stt-host:7272/stt/v1/stream

# Response
{"text": "hello world", "confidence": 0.92, "language": "en", "duration_ms": 800}
```

### Health & Monitoring

**GET** `/health` - Service health status
```bash
curl http://orac-stt-host:7272/health
# {"status":"healthy","timestamp":"2025-07-30T12:00:00Z","checks":{...}}
```

**GET** `/metrics` - Prometheus metrics
```bash
curl http://orac-stt-host:7272/metrics
# orac_stt_requests_total 42
# orac_stt_latency_seconds_histogram_bucket{le="0.5"} 38
```

### Supported Models

| Model Name | Size | Speed | Quality |
|------------|------|-------|---------|
| `tiny`     | 39MB | Fastest | Basic |
| `base`     | 147MB | Balanced | Good (default) |
| `small`    | 244MB | Slower | Better |

For detailed setup, deployment, and development information, see the `CURRENT_FOCUS.md` file.
