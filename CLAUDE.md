# ORAC STT - Claude Development Guide

## Project Overview
Speech-to-Text service for NVIDIA Orin Nano. Accepts audio streams, transcribes with Whisper models, forwards to Command API. Target: <500ms latency, <25% CPU on Orin Nano 8GB.

**Current Status**: Phase 1 complete (FastAPI, config, monitoring). See `CURRENT_FOCUS.md` for detailed progress.

## Development Environment

### Local Setup (Mac)
- **Working Directory**: `/Users/2oby/pCloud Box/Projects/ORAC STT`
- **Git Remote**: `https://github.com/2oby/ORAC-STT`
- **Python**: 3.10+ (Pydantic v2, FastAPI)
- **SSH Access**: `ssh orin4` (passwordless to Orin Nano)

### Orin Nano Target
- **Host**: `orin4` (NVIDIA Orin Nano 8GB)
- **OS**: Ubuntu 20.04 LTS (ARM64)
- **GPU**: CUDA 12.6, nvidia-smi available
- **Docker**: Enabled, supports `--gpus all`
- **User**: `toby` (deployment target: `/home/toby/orac-stt/`)

## Dependencies

The project uses split requirements files for better organization:

- **requirements.txt** - Core production dependencies (FastAPI, audio processing, etc.)
- **requirements-dev.txt** - Development tools (pytest, black, mypy, etc.)
- **requirements-pytorch.txt** - Optional PyTorch backend (not needed with whisper.cpp)

### Local Development Setup

For local development, install both production and dev dependencies:

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development tools
pip install -r requirements-dev.txt

# Optional: PyTorch backend (only if testing PyTorch support)
pip install -r requirements-pytorch.txt
```

### Running Tests Locally

Tests require dev dependencies:
```bash
# Install dev dependencies first
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Code Quality Tools

Dev dependencies include:
- **pytest** - Testing framework
- **pytest-asyncio** - Async test support
- **pytest-cov** - Coverage reporting
- **black** - Code formatting
- **isort** - Import sorting
- **mypy** - Type checking
- **flake8** - Linting

## Development Workflow

### 1. Code � Test Cycle
```bash
# Local development
git add . && git commit -m "feature: description"
git push origin master

# Deploy and test on Orin
cd scripts && ./deploy_and_test.sh
```

### 2. Deploy Script Flow (`deploy_and_test.sh`)
1. **Commit & Push**: Commits local changes and pushes to GitHub
2. **Pull on Orin**: Pulls latest code from GitHub to Orin Nano
3. **Build whisper.cpp**: Builds whisper.cpp if not already built (one-time)
4. **Deploy**: Uses `docker compose up -d --build` to build and start container
5. **Test**: Health check, metrics validation, log inspection
6. **Report**: Success/failure with container logs

### 3. Manual Operations
```bash
# Direct Orin commands via docker compose
ssh orin4 "cd /home/toby/orac-stt && docker compose ps"
ssh orin4 "cd /home/toby/orac-stt && docker compose logs -f"
ssh orin4 "curl http://localhost:7272/health"

# Container management
ssh orin4 "cd /home/toby/orac-stt && docker compose restart"
ssh orin4 "cd /home/toby/orac-stt && docker compose down"
ssh orin4 "cd /home/toby/orac-stt && docker compose up -d"
```

## Configuration

- **Template**: `config.toml.example` � copy to `config.toml` (gitignored)
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
ssh orin4 "cd /home/toby/orac-stt && docker compose logs --tail 20"

# Test endpoints
curl -s http://orin4:7272/health | jq .
curl -s http://orin4:7272/metrics | head -10

# Force rebuild (no cache)
ssh orin4 "cd /home/toby/orac-stt && docker compose build --no-cache && docker compose up -d"
```

## Performance Targets
- **Latency**: <500ms from audio end to text delivery
- **CPU**: <25% sustained on Orin Nano 8GB  
- **Memory**: Efficient model caching, minimal footprint
- **GPU**: CUDA acceleration for Whisper inference