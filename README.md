# ORAC STT Service

High-performance Speech-to-Text service optimized for NVIDIA Orin Nano. Provides fast, GPU-accelerated audio transcription using whisper.cpp with CUDA support.

**Version:** 0.2.0 | **Status:** Production Ready | **License:** MIT

---

## 🎯 Key Features

- **GPU-Accelerated Transcription**: whisper.cpp with CUDA support for Jetson/Orin hardware
- **Topic-Based Routing**: Multi-instance Hey ORAC support with automatic topic routing
- **Web Admin Dashboard**: Real-time monitoring with audio playback and command history
- **Heartbeat Management**: Automatic connection tracking and health monitoring
- **Production Ready**: Docker containerized, <500ms latency, <25% CPU usage
- **Small Footprint**: ~500MB container (vs 3-4GB PyTorch alternative)

---

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Documentation](#documentation)
- [Development](#development)
- [License](#license)

---

## 🚀 Quick Start

### For End Users

1. **Access the Web Dashboard**
   ```
   http://your-orin-ip:7272/admin/
   ```

2. **Monitor Transcriptions**
   - View real-time command feed
   - Play back audio recordings
   - Check connection status

### For Developers

```bash
# Clone repository
git clone https://github.com/2oby/ORAC-STT.git
cd ORAC-STT

# Deploy to Orin Nano
cd scripts
./deploy_and_test.sh

# Check service status
curl http://your-orin-ip:7272/health
```

---

## ✨ Features

### Speech-to-Text API
- **Endpoint**: `POST /stt/v1/stream/{topic}`
- **Audio Format**: 16kHz, 16-bit mono WAV/PCM
- **Response Time**: <500ms median latency
- **Topic Support**: Automatic routing based on wake word

### Topic System
- **Multi-Instance Support**: Multiple Hey ORAC instances per environment
- **Lazy Registration**: Topics auto-created from first heartbeat
- **Health Tracking**: Active/inactive status per topic
- **Flexible Routing**: Per-topic ORAC Core URL overrides

### Web Admin Interface
- **Real-Time Feed**: Live transcription updates via WebSocket
- **Audio Playback**: Built-in player for recorded commands
- **Command History**: Timestamped grid with confidence scores
- **Topic Monitoring**: Active topic list with last-seen timestamps
- **Responsive Design**: Works on desktop, tablet, and mobile

### Heartbeat System
- **Batched Updates**: Multiple wake word models per heartbeat
- **Automatic Forwarding**: Active models forwarded to ORAC Core
- **Health Status**: Real-time connection tracking
- **Topic Management**: API endpoints for topic CRUD operations

### Model Support
| Model | Size  | Speed    | Quality | Use Case |
|-------|-------|----------|---------|----------|
| tiny  | 39MB  | Fastest  | Basic   | Real-time, low latency |
| base  | 147MB | Balanced | Good    | General purpose (default) |
| small | 244MB | Slower   | Better  | Higher accuracy |

### Observability
- **Prometheus Metrics**: `/metrics` endpoint
- **Health Checks**: `/health` and `/stt/v1/health`
- **JSON Logging**: Structured logs for debugging
- **Debug Recordings**: Optional audio capture for analysis

---

## 📦 Requirements

### Hardware
- **NVIDIA Orin Nano** (8GB recommended)
- **GPU**: CUDA compute capability 8.7
- **Memory**: 2GB available RAM
- **Storage**: 5GB for models and container

### Software
- **OS**: Ubuntu 20.04+ (ARM64)
- **Docker**: 20.10+ with Docker Compose v2
- **CUDA**: 12.6 runtime
- **Network**: Access to GitHub for installation

### Optional
- **Python**: 3.10+ (for local development)
- **Build Tools**: cmake, build-essential (for whisper.cpp build)

---

## 🔧 Installation

### Option 1: Automated Deployment (Recommended)

```bash
# From your development machine
cd scripts
./deploy_and_test.sh
```

This script:
1. Commits and pushes code to GitHub
2. Pulls latest code on Orin Nano
3. Builds whisper.cpp (if needed)
4. Builds Docker container
5. Starts service via docker compose
6. Runs health checks

### Option 2: Manual Deployment

```bash
# 1. SSH to Orin Nano
ssh your-orin

# 2. Clone repository
git clone https://github.com/2oby/ORAC-STT.git
cd ORAC-STT

# 3. Build whisper.cpp (first time only)
cd third_party/whisper_cpp
./build_whisper_cpp.sh
cd ../..

# 4. Start service
docker compose up -d --build

# 5. Verify health
docker compose ps
curl http://localhost:7272/health
```

### whisper.cpp Build (First Time)

whisper.cpp is built directly on the Orin Nano:

```bash
cd third_party/whisper_cpp
./build_whisper_cpp.sh
```

**Build Time**: ~10-15 minutes (one-time)
**Requirements**: 8GB+ swap, sudo access

The script:
- Installs dependencies (cmake, build-essential, git)
- Clones whisper.cpp from GitHub
- Compiles with CUDA support (cuBLAS)
- Downloads GGML quantized models

---

## 📖 Usage

### Basic Transcription

```bash
# Transcribe an audio file
curl -X POST http://your-orin-ip:7272/stt/v1/stream/general \
  -F "file=@audio.wav" \
  -F "language=en"

# Response
{
  "text": "hello world",
  "confidence": 0.95,
  "language": "en",
  "duration": 1.2,
  "processing_time": 0.15
}
```

### Using Topics

```bash
# Transcribe with specific topic
curl -X POST http://your-orin-ip:7272/stt/v1/stream/computa \
  -F "file=@command.wav"

# Topic automatically forwards to ORAC Core
```

### Heartbeat (from Hey ORAC)

```bash
# Send heartbeat with active models
curl -X POST http://your-orin-ip:7272/stt/v1/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "hey-orac-pi-1",
    "models": [
      {"name": "computa", "wake_word": "hey computa", "is_active": true},
      {"name": "general", "wake_word": "hey orac", "is_active": true}
    ]
  }'
```

### Web Dashboard

Open `http://your-orin-ip:7272/admin/` for:
- Real-time command feed
- Audio playback
- Topic monitoring
- Connection status

---

## 🔌 API Reference

### Endpoints

#### Transcription
```
POST /stt/v1/stream/{topic}
```
Transcribe audio file and forward to ORAC Core.

**Parameters:**
- `topic` (path): Topic for routing (e.g., "general", "computa")
- `file` (form): Audio file (WAV, 16kHz, 16-bit, mono)
- `language` (form, optional): Language code (e.g., "en")
- `task` (form, optional): "transcribe" or "translate"

#### Heartbeat
```
POST /stt/v1/heartbeat
```
Receive batched heartbeat from Hey ORAC instances.

#### Health
```
GET /health
GET /stt/v1/health
GET /metrics
```

See [API_REFERENCE.md](./docs/API_REFERENCE.md) for detailed documentation.

---

## 📚 Documentation

- **[USER_GUIDE.md](./docs/USER_GUIDE.md)** - Deployment, configuration, and usage
- **[DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md)** - Architecture, development, and contributing
- **[API_REFERENCE.md](./docs/API_REFERENCE.md)** - Complete API documentation
- **[CHANGELOG.md](./CHANGELOG.md)** - Version history and changes

### Archived Documentation

Historical documentation is available in `docs/archive/`:
- Sprint completion reports
- Task prompts and analysis
- Development logs
- Solved issues

---

## 🛠️ Development

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/2oby/ORAC-STT.git
cd ORAC-STT

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy configuration template
cp config.toml.example config.toml

# Run locally (requires whisper.cpp)
python -m src.orac_stt.main
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/orac_stt --cov-report=html

# Run specific test file
pytest tests/unit/test_stt_handlers.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/
```

### Contributing

See [DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md) for:
- Project architecture
- Code style guidelines
- Testing standards
- Pull request process

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Hey ORAC Instances                  │
│  (Raspberry Pi with wake word detection)            │
└──────────────────┬──────────────────────────────────┘
                   │ Audio + Topic
                   ↓
┌─────────────────────────────────────────────────────┐
│              ORAC STT Service (Orin Nano)           │
│  ┌─────────────────────────────────────────────┐   │
│  │  FastAPI Server                              │   │
│  │  - /stt/v1/stream/{topic}                    │   │
│  │  - /stt/v1/heartbeat                         │   │
│  │  - /admin/ (Web Dashboard)                   │   │
│  └──────────────────┬──────────────────────────┘   │
│                     ↓                                │
│  ┌─────────────────────────────────────────────┐   │
│  │  whisper.cpp (CUDA-accelerated)             │   │
│  │  - GGML quantized models                     │   │
│  │  - GPU inference via cuBLAS                  │   │
│  └──────────────────┬──────────────────────────┘   │
│                     ↓                                │
│  ┌─────────────────────────────────────────────┐   │
│  │  Topic Registry + Command Buffer             │   │
│  │  - Lazy registration                         │   │
│  │  - Heartbeat tracking                        │   │
│  └──────────────────┬──────────────────────────┘   │
└────────────────────┬────────────────────────────────┘
                     │ Text + Metadata
                     ↓
┌─────────────────────────────────────────────────────┐
│              ORAC Core (LLM Processing)             │
│  (Command parsing and response generation)          │
└─────────────────────────────────────────────────────┘
```

---

## 🔒 Security

- **mTLS Support**: Mutual TLS for secure communication (planned)
- **Token Authentication**: Bearer token support (optional)
- **Network Isolation**: Docker bridge network
- **Resource Limits**: Memory and CPU constraints via Docker
- **Input Validation**: Audio format and duration checks

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs orac-stt

# Verify whisper.cpp
docker compose exec orac-stt ls -la /app/third_party/whisper_cpp/bin/

# Check GPU access
docker compose exec orac-stt nvidia-smi
```

### Health Check Failing

```bash
# Test from inside container
docker compose exec orac-stt curl http://localhost:7272/health

# Check if service is listening
docker compose exec orac-stt netstat -tulpn | grep 7272
```

### Poor Performance

```bash
# Check GPU usage
nvidia-smi

# Monitor container resources
docker stats orac-stt

# Review logs for errors
docker compose logs --tail 100 orac-stt
```

See [USER_GUIDE.md](./docs/USER_GUIDE.md) for detailed troubleshooting.

---

## 📊 Performance

- **Latency**: <500ms from audio end to text (15s audio)
- **CPU Usage**: <25% sustained on Orin Nano 8GB
- **Memory**: <2GB RAM for base model
- **Throughput**: ~50 requests/second (model-dependent)
- **Container Size**: ~500MB (vs 3-4GB with PyTorch)

---

## 🗺️ Roadmap

### v0.3.0 (Next Release)
- [ ] WebSocket streaming transcription
- [ ] Batch processing endpoint
- [ ] Enhanced metrics dashboard
- [ ] Unit test coverage >80%

### v0.4.0 (Future)
- [ ] Multiple model support (concurrent)
- [ ] Custom model upload
- [ ] Speaker diarization
- [ ] Word-level timestamps

See [DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md) for full roadmap.

---

## 📄 License

MIT License - See [LICENSE](./LICENSE) for details.

---

## 🙏 Acknowledgments

- **whisper.cpp**: [ggerganov/whisper.cpp](https://github.com/ggerganov/whisper.cpp)
- **OpenAI Whisper**: [openai/whisper](https://github.com/openai/whisper)
- **FastAPI**: [tiangolo/fastapi](https://github.com/tiangolo/fastapi)

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/2oby/ORAC-STT/issues)
- **Documentation**: [docs/](./docs/)
- **Discussions**: [GitHub Discussions](https://github.com/2oby/ORAC-STT/discussions)

---

**Built with ❤️ for the ORAC ecosystem**
