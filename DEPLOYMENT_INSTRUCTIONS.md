# ORAC STT Deployment Instructions

## Overview

ORAC STT is deployed to NVIDIA Orin Nano using Docker Compose for streamlined container management. The service uses whisper.cpp for GPU-accelerated speech transcription with CUDA support.

## Quick Start

### Automated Deployment (Recommended)

The `deploy_and_test.sh` script handles the entire deployment pipeline:

```bash
cd scripts
./deploy_and_test.sh
```

This script will:
1. Commit and push local changes to GitHub
2. Pull latest code on Orin Nano
3. Build whisper.cpp if not already built
4. Build Docker image and start container via docker compose
5. Run health checks and display logs

### Manual Deployment

If you prefer manual control:

```bash
# 1. Push code to GitHub
git add -A
git commit -m "Your commit message"
git push origin cleanup/phase-1-foundation

# 2. SSH to Orin and pull latest code
ssh orin4
cd /home/toby/orac-stt
git pull origin cleanup/phase-1-foundation

# 3. Build whisper.cpp (first time only)
cd third_party/whisper_cpp
./build_whisper_cpp.sh
cd /home/toby/orac-stt

# 4. Deploy using docker compose
docker compose down
docker compose up -d --build

# 5. Check status
docker compose ps
docker compose logs -f
curl http://localhost:7272/health
```

## Docker Image Dependencies

The production Docker image installs only `requirements.txt` (core dependencies).

**Included:**
- FastAPI and Uvicorn (web framework)
- Audio processing libraries (numpy, scipy, librosa, soundfile)
- Configuration libraries (toml, PyYAML)
- Prometheus metrics client
- aiohttp for HTTP client

**NOT Included:**
- Development dependencies (`requirements-dev.txt`) - Excluded to keep image small
- PyTorch dependencies (`requirements-pytorch.txt`) - Not needed because we use whisper.cpp

### Image Size Comparison

- **With only requirements.txt:** ~500MB
- **With requirements-pytorch.txt:** ~3-4GB (not recommended)

### Building with Optional Dependencies

If you need to build with PyTorch support for testing:

1. **Edit Dockerfile** and uncomment:
```dockerfile
# Uncomment these lines:
COPY requirements-pytorch.txt .
RUN python3.10 -m pip install --no-cache-dir -r requirements-pytorch.txt
```

2. **Set environment variable** in docker compose.yml:
```yaml
environment:
  - USE_WHISPER_CPP=false
```

3. **Rebuild:**
```bash
docker compose up -d --build
```

## Docker Compose Configuration

The `docker compose.yml` file provides:

### GPU Support
- Runtime: nvidia
- CUDA 12.6 runtime container
- Full GPU access via `NVIDIA_VISIBLE_DEVICES=all`

### Volume Mounts
- **models**: Persistent model cache
- **logs**: Application logs
- **certs**: TLS certificates
- **data**: Application data
- **debug_recordings**: Audio recordings for debugging
- **third_party/whisper_cpp**: Pre-built whisper.cpp binaries and libraries

### Environment Variables
Key configuration via environment:
- `ORAC_COMMAND_API_URL`: Downstream API endpoint
- `ORAC_API_PORT`: Service port (7272)
- `USE_WHISPER_CPP`: Enable whisper.cpp backend (true)
- `LD_LIBRARY_PATH`: Path to whisper.cpp shared libraries

### Resource Limits
- Memory limit: 2GB
- Memory reservation: 1GB
- Suitable for Orin Nano 8GB

## whisper.cpp Setup

### First-Time Build

whisper.cpp must be built directly on the Orin Nano:

```bash
ssh orin4
cd /home/toby/orac-stt/third_party/whisper_cpp
./build_whisper_cpp.sh
```

**Build time:** ~10-15 minutes (one-time)
**Requirements:** 8GB+ swap, sudo access

The build script:
1. Installs dependencies (cmake, build-essential, git)
2. Clones whisper.cpp from GitHub
3. Compiles with CUDA support (cuBLAS)
4. Downloads GGML quantized models (tiny, base, small)

### Verification

After building, verify binaries exist:
```bash
ls -la /home/toby/orac-stt/third_party/whisper_cpp/bin/whisper-cli
ls -la /home/toby/orac-stt/third_party/whisper_cpp/lib/*.so*
```

The Docker container mounts these directories at runtime.

## Health Checks

### Service Health
```bash
curl http://orin4:7272/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-17T12:00:00Z",
  "checks": {
    "service": "ok"
  }
}
```

### Metrics Endpoint
```bash
curl http://orin4:7272/metrics
```

Should return Prometheus-format metrics:
```
orac_stt_requests_total 42
orac_stt_latency_seconds_histogram_bucket{le="0.5"} 38
```

### STT Health
```bash
curl http://orin4:7272/stt/v1/health
```

## Container Management

### View Logs
```bash
# Follow logs (real-time)
docker compose logs -f

# Last 50 lines
docker compose logs --tail 50

# Specific service
docker compose logs -f orac-stt
```

### Restart Service
```bash
# Restart without rebuilding
docker compose restart

# Stop and start
docker compose down
docker compose up -d
```

### Rebuild Container
```bash
# Full rebuild (after code changes)
docker compose up -d --build

# Force rebuild from scratch
docker compose build --no-cache
docker compose up -d
```

### Shell Access
```bash
# Access running container
docker compose exec orac-stt bash

# One-time command
docker compose exec orac-stt python3.10 -c "import uvicorn; print(uvicorn.__version__)"
```

## Troubleshooting

### Container Won't Start

1. **Check logs:**
```bash
docker compose logs orac-stt
```

2. **Verify dependencies:**
```bash
docker compose exec orac-stt python3.10 -c "import uvicorn, fastapi; print('OK')"
```

3. **Check whisper.cpp:**
```bash
docker compose exec orac-stt ls -la /app/third_party/whisper_cpp/bin/
docker compose exec orac-stt ls -la /usr/local/lib/whisper/
```

### Health Check Failing

1. **Check if service is listening:**
```bash
docker compose exec orac-stt netstat -tulpn | grep 7272
```

2. **Test from inside container:**
```bash
docker compose exec orac-stt curl http://localhost:7272/health
```

3. **Check GPU access:**
```bash
docker compose exec orac-stt nvidia-smi
```

### Import Errors

If you see `ModuleNotFoundError`:

1. **Verify requirements.txt is complete:**
```bash
cat requirements.txt
```

2. **Rebuild without cache:**
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

3. **Check pip list inside container:**
```bash
docker compose exec orac-stt pip list
```

### High Memory Usage

1. **Check resource usage:**
```bash
docker stats orac-stt
```

2. **Adjust limits in docker compose.yml:**
```yaml
deploy:
  resources:
    limits:
      memory: 3G  # Increase if needed
```

## Configuration

### Environment Overrides

Override config via docker compose.yml:

```yaml
environment:
  - ORAC_LOG_LEVEL=DEBUG
  - ORAC_MODEL_NAME=whisper-base
  - ORAC_COMMAND_API_URL=http://custom-api:8080
```

### Config File

Alternatively, mount a custom config.toml:

```yaml
volumes:
  - ./my-config.toml:/app/config.toml:ro
```

## Performance Targets

- **Latency:** <500ms from audio end to text delivery
- **CPU:** <25% sustained on Orin Nano 8GB
- **Memory:** <2GB RAM
- **GPU:** CUDA acceleration for Whisper inference

## Security

### mTLS Certificates

For production, generate and mount certificates:

```bash
# Generate certs (placeholder - implement as needed)
mkdir -p certs
# Add cert generation script here

# Mount in docker compose.yml (already configured)
volumes:
  - ./certs:/app/certs:ro
```

### Network Security

The service binds to all interfaces (0.0.0.0:7272) by default. For production:

1. Use a reverse proxy (nginx, traefik)
2. Enable mTLS in config.toml
3. Restrict network access via firewall rules

## Maintenance

### Update Dependencies

After modifying requirements.txt:

```bash
git add requirements.txt
git commit -m "chore: update dependencies"
git push
cd scripts && ./deploy_and_test.sh
```

### Update whisper.cpp

To update to latest whisper.cpp:

```bash
ssh orin4
cd /home/toby/orac-stt/third_party/whisper_cpp
rm -rf whisper.cpp/
./build_whisper_cpp.sh
```

### Backup Data

Important directories to back up:
- `models/` - Model cache
- `logs/` - Application logs
- `certs/` - TLS certificates
- `data/` - Application data

## Next Steps

After successful deployment:

1. Test STT endpoint with audio samples
2. Configure ORAC Core integration
3. Set up monitoring (Prometheus/Grafana)
4. Enable mTLS for security
5. Configure log rotation

## References

- **Development Guide:** `CLAUDE.md`
- **Project Status:** `CURRENT_FOCUS.md`
- **Configuration:** `config.toml.example`
- **Deployment Script:** `scripts/deploy_and_test.sh`
