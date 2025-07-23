# ORAC STT - Claude Development Guide

## Project Overview
Speech-to-Text service for NVIDIA Orin Nano. Accepts audio streams, transcribes with Whisper models, forwards to Command API. Target: <500ms latency, <25% CPU on Orin Nano 8GB.

**Current Status**: Phase 1 complete (FastAPI, config, monitoring). See `CURRENT_FOCUS.md` for detailed progress.

## Development Environment

### Local Setup (Mac)
- **Working Directory**: `/Users/2oby/pCloud Box/Projects/ORAC STT`
- **Git Remote**: `https://github.com/2oby/ORAC-STT`
- **Python**: 3.10+ (Pydantic v2, FastAPI)
- **SSH Access**: `ssh orin3` (passwordless to Orin Nano)

### Orin Nano Target
- **Host**: `orin3` (NVIDIA Orin Nano 8GB)
- **OS**: Ubuntu 20.04 LTS (ARM64)
- **GPU**: CUDA 12.6, nvidia-smi available
- **Docker**: Enabled, supports `--gpus all`
- **User**: `toby` (deployment target: `/home/toby/orac-stt/`)

## Development Workflow

### 1. Code ’ Test Cycle
```bash
# Local development
git add . && git commit -m "feature: description"
git push origin master

# Deploy and test on Orin
cd scripts && ./deploy_and_test.sh
```

### 2. Deploy Script Flow (`deploy_and_test.sh`)
1. **Sync**: `rsync` project files to `orin3:/home/toby/orac-stt/`
2. **Build**: `docker build -t orac-stt:latest .` on Orin
3. **Deploy**: Stop old container, start new with volume mounts
4. **Test**: Health check, metrics validation, log inspection
5. **Report**: Success/failure with container logs

### 3. Manual Operations
```bash
# Direct Orin commands
ssh orin3 "docker ps | grep orac-stt"
ssh orin3 "docker logs -f orac-stt"
ssh orin3 "curl http://localhost:8000/health"

# Container management
ssh orin3 "docker stop orac-stt && docker rm orac-stt"
```

## Configuration

- **Template**: `config.toml.example` ’ copy to `config.toml` (gitignored)
- **Overrides**: Environment variables with `ORAC_` prefix
- **Container**: Config copied as `/app/config.toml`, volumes mounted for models/logs/certs

## Key Files

- **`src/orac_stt/main.py`**: FastAPI application entry point
- **`Dockerfile`**: Minimal Python 3.10-slim, core dependencies only
- **`scripts/deploy_and_test.sh`**: Full deployment pipeline
- **`CURRENT_FOCUS.md`**: Detailed project status and next tasks
- **`config.toml.example`**: Configuration template with documentation

## Architecture Status

** Working**: FastAPI server, health/metrics endpoints, JSON logging, TOML config, Docker deployment  
**= Next**: GPU support, PyTorch/Whisper installation, `/stt/v1/stream` endpoint implementation

## Quick Commands

```bash
# Deploy latest changes
cd scripts && ./deploy_and_test.sh

# Check logs
ssh orin3 "docker logs --tail 20 orac-stt"

# Test endpoints
curl -s http://orin3:8000/health | jq .
curl -s http://orin3:8000/metrics | head -10

# Force rebuild (no cache)
ssh orin3 "cd /home/toby/orac-stt && docker build --no-cache -t orac-stt ."
```

## Performance Targets
- **Latency**: <500ms from audio end to text delivery
- **CPU**: <25% sustained on Orin Nano 8GB  
- **Memory**: Efficient model caching, minimal footprint
- **GPU**: CUDA acceleration for Whisper inference