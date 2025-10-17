# ORAC STT User Guide

Complete guide for deploying, configuring, and using the ORAC STT Service on NVIDIA Orin Nano.

**Version:** 0.2.0 | **Last Updated:** October 17, 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Deployment](#deployment)
6. [Using the Service](#using-the-service)
7. [Web Admin Dashboard](#web-admin-dashboard)
8. [Monitoring](#monitoring)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## Overview

ORAC STT is a high-performance speech-to-text service that runs on NVIDIA Orin Nano hardware. It provides:

- **GPU-accelerated transcription** using whisper.cpp with CUDA
- **Topic-based routing** for multiple Hey ORAC instances
- **Real-time web dashboard** for monitoring
- **Automatic heartbeat tracking** and health management

### System Architecture

```
Hey ORAC (Raspberry Pi) → ORAC STT (Orin Nano) → ORAC Core (LLM)
   Wake Word Detection      Speech-to-Text        Command Processing
```

---

## Prerequisites

### Hardware Requirements

- **NVIDIA Orin Nano** (8GB recommended)
- **GPU**: CUDA compute capability 8.7
- **RAM**: Minimum 4GB available (8GB recommended)
- **Storage**: 5GB available for models and container
- **Network**: Ethernet or WiFi with stable connection

### Software Requirements

- **Operating System**: Ubuntu 20.04 or 22.04 (ARM64)
- **Docker**: Version 20.10 or higher
- **Docker Compose**: v2 (comes with Docker Engine)
- **CUDA**: 12.6 runtime (usually pre-installed on Orin)
- **Git**: For cloning the repository

### Network Access

- SSH access to the Orin Nano
- Internet access for downloading models (first time)
- Access to GitHub for cloning repository

---

## Installation

### Step 1: Prepare the Orin Nano

```bash
# SSH to your Orin Nano
ssh your-orin-username@your-orin-ip

# Verify Docker is installed
docker --version
docker compose version

# Verify CUDA is available
nvidia-smi
```

### Step 2: Clone the Repository

```bash
# Navigate to your preferred directory
cd /home/your-username

# Clone the repository
git clone https://github.com/2oby/ORAC-STT.git
cd ORAC-STT

# Checkout the correct branch (if needed)
git checkout cleanup/phase-1-foundation
```

### Step 3: Build whisper.cpp (First Time Only)

whisper.cpp must be built directly on the Orin Nano with CUDA support:

```bash
cd third_party/whisper_cpp
./build_whisper_cpp.sh
```

**What this script does:**
1. Installs build dependencies (cmake, build-essential, git)
2. Clones whisper.cpp from GitHub
3. Compiles with CUDA/cuBLAS support
4. Downloads GGML quantized models (tiny, base, small)

**Build time:** ~10-15 minutes (one-time setup)

**Requirements:**
- Sudo access for installing dependencies
- 8GB+ swap space recommended
- Stable internet connection

**Troubleshooting Build Issues:**

If build fails, check:
```bash
# Verify CUDA toolkit
nvcc --version

# Check available disk space
df -h

# Check swap
free -h
```

### Step 4: Verify Installation

After build completes, verify:

```bash
# Check binaries
ls -la /home/your-username/ORAC-STT/third_party/whisper_cpp/bin/
# Should see: whisper-cli, quantize, whisper-server, etc.

# Check shared libraries
ls -la /home/your-username/ORAC-STT/third_party/whisper_cpp/lib/
# Should see: libwhisper.so*

# Check models
ls -la /home/your-username/ORAC-STT/third_party/whisper_cpp/models/
# Should see: ggml-tiny.bin, ggml-base.bin, ggml-small.bin
```

---

## Configuration

### Configuration File

The service uses a TOML configuration file with environment variable overrides.

**Copy the template:**
```bash
cp config.toml.example config.toml
```

**Edit configuration:**
```bash
nano config.toml
```

### Key Configuration Sections

#### 1. Application Settings
```toml
[app]
log_level = "INFO"           # DEBUG, INFO, WARNING, ERROR
environment = "production"    # development, staging, production
```

#### 2. Model Settings
```toml
[model]
name = "whisper-base"         # tiny, base, small
device = "cuda"               # cuda or cpu
cache_dir = "/app/models"
```

#### 3. API Settings
```toml
[api]
host = "0.0.0.0"
port = 7272
request_timeout = 30
max_audio_duration = 15       # seconds
```

#### 4. ORAC Core Integration
```toml
[command_api]
url = "http://localhost:8001/command"
timeout = 5
retry_attempts = 3
```

### Environment Variable Overrides

Override any setting using `ORAC_` prefix:

```bash
export ORAC_LOG_LEVEL=DEBUG
export ORAC_MODEL_NAME=whisper-tiny
export ORAC_COMMAND_API_URL=http://192.168.1.100:8001/command
```

In docker-compose.yml:
```yaml
environment:
  - ORAC_LOG_LEVEL=DEBUG
  - ORAC_MODEL_NAME=whisper-base
```

---

## Deployment

### Method 1: Automated Deployment (Recommended)

From your **development machine** (not the Orin):

```bash
cd scripts
./deploy_and_test.sh
```

This script:
1. Commits local changes
2. Pushes to GitHub
3. Pulls latest code on Orin
4. Builds whisper.cpp (if needed)
5. Builds Docker container
6. Starts service via docker compose
7. Runs health checks
8. Displays logs

### Method 2: Manual Deployment

On the **Orin Nano**:

```bash
# Navigate to project directory
cd /home/your-username/ORAC-STT

# Pull latest changes
git pull origin cleanup/phase-1-foundation

# Stop existing container
docker compose down

# Build and start new container
docker compose up -d --build

# Check status
docker compose ps
docker compose logs -f
```

### Docker Compose Configuration

The `docker-compose.yml` file provides:

**GPU Support:**
- CUDA 12.6 runtime container
- Full GPU access via nvidia runtime

**Volume Mounts:**
- `./models:/app/models` - Persistent model cache
- `./logs:/app/logs` - Application logs
- `./data:/app/data` - Application data (topic registry)
- `./debug_recordings:/app/debug_recordings` - Debug audio files
- `./third_party/whisper_cpp:/usr/local/lib/whisper` - whisper.cpp binaries

**Resource Limits:**
- Memory limit: 2GB
- Memory reservation: 1GB

**Environment Variables:**
- `TZ=Europe/Zurich` - Timezone
- `USE_WHISPER_CPP=true` - Enable whisper.cpp backend
- `ORAC_COMMAND_API_URL` - Downstream API endpoint

### First Deployment Verification

After first deployment, verify:

```bash
# 1. Check container is running
docker compose ps
# Should show "Up (healthy)"

# 2. Check logs
docker compose logs --tail 50

# 3. Test health endpoint
curl http://localhost:7272/health

# 4. Test STT health
curl http://localhost:7272/stt/v1/health

# 5. Check GPU access
docker compose exec orac-stt nvidia-smi

# 6. Test admin interface
# Open http://your-orin-ip:7272/admin/ in browser
```

---

## Using the Service

### Basic Transcription

**Transcribe an audio file:**

```bash
curl -X POST http://your-orin-ip:7272/stt/v1/stream/general \
  -F "file=@your-audio.wav" \
  -F "language=en"
```

**Response:**
```json
{
  "text": "hello world",
  "confidence": 0.95,
  "language": "en",
  "duration": 1.2,
  "processing_time": 0.15
}
```

### Topic-Based Routing

**Transcribe with specific topic:**

```bash
curl -X POST http://your-orin-ip:7272/stt/v1/stream/computa \
  -F "file=@command.wav"
```

The transcription is automatically forwarded to ORAC Core with the topic metadata.

**Supported topics:**
- `general` - Default topic
- `computa` - Custom topic
- Any topic name (auto-registered on first use)

### Audio Requirements

**Mandatory format:**
- **Format**: WAV (PCM)
- **Sample Rate**: 16 kHz (16000 Hz)
- **Bit Depth**: 16-bit
- **Channels**: Mono (1 channel)
- **Maximum Duration**: 15 seconds

**Converting audio to required format:**

```bash
# Using ffmpeg
ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 output.wav

# Using sox
sox input.mp3 -r 16000 -c 1 -b 16 output.wav
```

### Heartbeat System (for Hey ORAC)

Hey ORAC instances send periodic heartbeats to register their wake word models:

```bash
curl -X POST http://your-orin-ip:7272/stt/v1/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "hey-orac-pi-1",
    "models": [
      {
        "name": "computa",
        "wake_word": "hey computa",
        "is_active": true,
        "last_triggered": "2025-10-17T22:30:00Z"
      },
      {
        "name": "general",
        "wake_word": "hey orac",
        "is_active": true,
        "last_triggered": "2025-10-17T22:29:45Z"
      }
    ]
  }'
```

**Response:**
```json
{
  "status": "success",
  "registered_topics": ["computa", "general"],
  "forwarded_to_core": true
}
```

---

## Web Admin Dashboard

### Accessing the Dashboard

Open in your web browser:
```
http://your-orin-ip:7272/admin/
```

### Dashboard Features

#### 1. Connection Status
- **"Dashboard Connected"** (green) - WebSocket active
- **"Dashboard Disconnected"** (red) - Connection lost

#### 2. Active Topics Panel
- List of all registered topics
- Last seen timestamp for each topic
- Active/inactive status indicator
- Topic-specific metadata

#### 3. Command Feed
Real-time transcription feed showing:
- **Timestamp** - When the command was received (HH:MM format)
- **Confidence** - Transcription confidence score (%)
- **Text** - Transcribed speech
- **Duration** - Audio file duration
- **Audio Player** - Play/pause button for each recording

#### 4. Command Cards

Each command displays as a card with:
```
┌─────────────────────────────────────┐
│ 22:30                      95%      │
│ hello world                         │
│ 1.2s                          ▶️    │
└─────────────────────────────────────┘
```

- **Top left**: Timestamp
- **Top right**: Confidence score
- **Middle**: Transcribed text
- **Bottom left**: Duration
- **Bottom right**: Play button

#### 5. Auto-Refresh
- New commands appear in real-time via WebSocket
- No page refresh required
- Maximum 50 commands displayed at once
- Older commands automatically removed

### Dashboard Tips

- **Audio playback**: Click the play button to hear recorded audio
- **Connection issues**: If "Disconnected" appears, refresh the page
- **Mobile access**: Dashboard is responsive and works on mobile devices
- **Multiple viewers**: Multiple browsers can view dashboard simultaneously

---

## Monitoring

### Health Endpoints

#### Service Health
```bash
curl http://your-orin-ip:7272/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.2.0",
  "timestamp": "2025-10-17T22:30:00Z"
}
```

#### STT Health
```bash
curl http://your-orin-ip:7272/stt/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "model_name": "whisper-base",
  "backend": "whisper.cpp",
  "device": "cuda"
}
```

### Prometheus Metrics

```bash
curl http://your-orin-ip:7272/metrics
```

**Key metrics:**
- `orac_stt_requests_total` - Total transcription requests
- `orac_stt_latency_seconds` - Processing latency histogram
- `orac_stt_errors_total` - Total errors
- `orac_stt_active_topics` - Number of active topics

### Container Logs

```bash
# Follow logs in real-time
docker compose logs -f

# Last 100 lines
docker compose logs --tail 100

# Filter by log level
docker compose logs | grep ERROR

# Save logs to file
docker compose logs > logs_$(date +%Y%m%d_%H%M%S).txt
```

### Resource Monitoring

```bash
# Container resource usage
docker stats orac-stt

# GPU usage
nvidia-smi

# GPU monitoring (continuous)
watch -n 1 nvidia-smi

# System resources
htop
```

---

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker compose logs orac-stt
```

**Common issues:**

1. **Port already in use (7272)**
   ```bash
   # Find process using port
   sudo lsof -i :7272

   # Kill process or change port in docker-compose.yml
   ```

2. **whisper.cpp not found**
   ```bash
   # Verify binaries exist
   ls -la third_party/whisper_cpp/bin/whisper-cli

   # Rebuild if missing
   cd third_party/whisper_cpp && ./build_whisper_cpp.sh
   ```

3. **GPU access denied**
   ```bash
   # Verify Docker has GPU access
   docker run --rm --gpus all nvidia/cuda:12.6.0-runtime-ubuntu22.04 nvidia-smi

   # Check nvidia-docker runtime
   sudo systemctl status nvidia-docker
   ```

### Health Check Failing

**Test from inside container:**
```bash
docker compose exec orac-stt curl http://localhost:7272/health
```

**Check if service is listening:**
```bash
docker compose exec orac-stt netstat -tulpn | grep 7272
```

**Check process is running:**
```bash
docker compose exec orac-stt ps aux | grep python
```

### Poor Transcription Performance

**1. Check GPU is being used:**
```bash
# During transcription, GPU usage should spike
nvidia-smi
```

**2. Switch to smaller model:**
```yaml
# In docker-compose.yml
environment:
  - ORAC_MODEL_NAME=whisper-tiny  # Faster but less accurate
```

**3. Check CPU/memory:**
```bash
docker stats orac-stt
```

**4. Review logs for errors:**
```bash
docker compose logs --tail 200 | grep ERROR
```

### Audio Format Errors

**Error: "Audio must be mono (1 channel)"**
```bash
# Convert to mono
ffmpeg -i input.wav -ac 1 output.wav
```

**Error: "Sample rate must be 16000 Hz"**
```bash
# Convert sample rate
ffmpeg -i input.wav -ar 16000 output.wav
```

**Error: "Audio duration exceeds 15 seconds"**
```bash
# Trim audio
ffmpeg -i input.wav -t 15 output.wav
```

### Dashboard Not Loading

**1. Check service is running:**
```bash
curl http://your-orin-ip:7272/health
```

**2. Check browser console for errors:**
- Open browser DevTools (F12)
- Check Console tab for JavaScript errors
- Check Network tab for failed requests

**3. Clear browser cache:**
- Hard refresh: Ctrl+Shift+R (Linux/Windows) or Cmd+Shift+R (Mac)

**4. Check WebSocket connection:**
```bash
# In browser console
ws = new WebSocket('ws://your-orin-ip:7272/ws')
```

### High Memory Usage

**Check current usage:**
```bash
docker stats orac-stt
```

**Adjust memory limits:**
```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      memory: 3G  # Increase if needed
```

**Clear old recordings:**
```bash
# Debug recordings are limited to 5 by default
ls -lh debug_recordings/

# Manual cleanup if needed
rm debug_recordings/debug_*.wav
```

---

## Maintenance

### Updating the Service

```bash
# Pull latest code
git pull origin cleanup/phase-1-foundation

# Rebuild and restart
docker compose down
docker compose up -d --build

# Verify health
curl http://localhost:7272/health
```

### Updating whisper.cpp

```bash
# Remove old build
cd third_party/whisper_cpp
rm -rf whisper.cpp/

# Rebuild
./build_whisper_cpp.sh

# Restart service
cd ../..
docker compose restart
```

### Backing Up Data

**Important directories:**

```bash
# Backup script
tar -czf orac-stt-backup-$(date +%Y%m%d).tar.gz \
  models/ \
  data/ \
  logs/ \
  certs/ \
  config.toml
```

**Restore from backup:**
```bash
tar -xzf orac-stt-backup-YYYYMMDD.tar.gz
docker compose restart
```

### Log Rotation

Logs are automatically rotated by Docker:

```yaml
# In docker-compose.yml (already configured)
logging:
  driver: "json-file"
  options:
    max-size: "10m"    # Max file size
    max-file: "3"      # Keep 3 files
```

**Manual log cleanup:**
```bash
# View log file sizes
docker inspect orac-stt --format='{{.LogPath}}'

# Truncate logs
docker compose down
truncate -s 0 $(docker inspect orac-stt --format='{{.LogPath}}')
docker compose up -d
```

### Updating Dependencies

After modifying `requirements.txt`:

```bash
git add requirements.txt
git commit -m "chore: update dependencies"
git push

# Rebuild with no cache
docker compose build --no-cache
docker compose up -d
```

---

## Advanced Topics

### Custom Model Configuration

To use a different Whisper model:

```bash
# Download model (on Orin)
cd third_party/whisper_cpp/models
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin

# Update configuration
# In docker-compose.yml or config.toml:
environment:
  - ORAC_MODEL_NAME=whisper-medium
```

### Per-Topic Core URL Override

Set different ORAC Core URLs for different topics:

```bash
# Via API
curl -X POST http://your-orin-ip:7272/topics/computa/core-url \
  -H "Content-Type: application/json" \
  -d '{"core_url": "http://192.168.1.100:8001/command"}'

# Now "computa" topic will use custom URL
# Other topics use default from config
```

### Debug Recordings

Debug recordings are automatically saved for the last 5 transcriptions:

```bash
# List recordings
curl http://your-orin-ip:7272/stt/v1/debug/recordings

# Download specific recording
curl http://your-orin-ip:7272/stt/v1/debug/recordings/debug_20251017_223000_hello.wav \
  -o recording.wav
```

**Disable debug recordings:**
```yaml
# In docker-compose.yml
environment:
  - ORAC_ENABLE_DEBUG_RECORDINGS=false
```

---

## Performance Optimization

### Best Practices

1. **Model Selection**
   - Use `whisper-tiny` for real-time, low-latency
   - Use `whisper-base` for balanced performance (default)
   - Use `whisper-small` for higher accuracy

2. **GPU Utilization**
   - Monitor GPU usage with `nvidia-smi`
   - Ensure GPU isn't throttling due to temperature
   - Keep GPU drivers updated

3. **Network**
   - Use wired Ethernet for stable connection
   - Minimize network latency to ORAC Core
   - Consider running ORAC Core on same network

4. **Resource Allocation**
   - Allocate at least 2GB RAM to container
   - Ensure sufficient swap space (8GB+)
   - Monitor disk space for logs and recordings

### Performance Targets

- **Latency**: <500ms from audio end to text (15s audio)
- **CPU**: <25% sustained on Orin Nano 8GB
- **Memory**: <2GB RAM for base model
- **GPU**: 30-50% utilization during transcription

---

## Security Best Practices

### Network Security

1. **Use firewall to restrict access:**
   ```bash
   sudo ufw allow from 192.168.1.0/24 to any port 7272
   ```

2. **Enable mTLS** (when available):
   ```toml
   [security]
   enable_mtls = true
   cert_file = "/app/certs/server.crt"
   key_file = "/app/certs/server.key"
   ```

3. **Use reverse proxy** (nginx, traefik) for HTTPS

### Data Security

- **Disable debug recordings** in production
- **Rotate logs** regularly
- **Backup certificates** securely
- **Use environment variables** for secrets (not config files)

---

## Getting Help

### Documentation

- **API Reference**: [API_REFERENCE.md](./API_REFERENCE.md)
- **Developer Guide**: [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)
- **README**: [../README.md](../README.md)

### Support Channels

- **GitHub Issues**: [ORAC-STT Issues](https://github.com/2oby/ORAC-STT/issues)
- **GitHub Discussions**: [ORAC-STT Discussions](https://github.com/2oby/ORAC-STT/discussions)

### Reporting Issues

When reporting issues, include:

1. **Environment info:**
   ```bash
   docker compose version
   nvidia-smi
   uname -a
   ```

2. **Container logs:**
   ```bash
   docker compose logs --tail 200 > logs.txt
   ```

3. **Error messages** and steps to reproduce

4. **Configuration** (redact secrets)

---

**Last Updated:** October 17, 2025
**Version:** 0.2.0
**Author:** ORAC Team
