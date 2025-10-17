# ORAC STT Solved Issues

## Issue: Docker Container Won't Start - Missing Python Dependencies
**Date**: 2025-09-07  
**Status**: SOLVED ✅

### Symptoms
- Container crashes immediately with: `ModuleNotFoundError: No module named 'uvicorn'`
- Despite multiple rebuild attempts, Python dependencies weren't accessible
- Docker builds appeared successful but container failed at runtime

### The Root Cause

1. **Failed whisper.cpp build**: Originally, the Dockerfile tried to build whisper.cpp from source inside the container, which failed
2. **Cached broken layers**: When that was removed from the Dockerfile, Docker reused cached layers from earlier builds
3. **Missing Python dependencies**: Those cached layers didn't have the Python packages (uvicorn, fastapi, etc.) properly installed

### Why Previous Attempts Failed

- Docker was using `CACHED` layers that looked successful but were actually broken
- The Python dependencies were either:
  - Never installed in those cached layers, OR  
  - Installed in a way that wasn't accessible to python3.10

### The Fix

1. **Force clean rebuild**: Used `--no-cache` flag to bypass all cached layers
2. **Explicit Python version**: Used `python3.10 -m pip install` instead of just `pip install`
3. **Verification steps**: Added checks to confirm packages were installed during build
4. **External whisper.cpp**: Mounted pre-built binaries from host instead of building in container

### Solution Files Created
- `Dockerfile.fixed` - Clean Dockerfile with explicit python3.10 usage
- `docker-compose.fixed.yml` - Mounts whisper.cpp from host
- `scripts/fix_orac_stt.sh` - Automated deployment with --no-cache

### Key Commands
```bash
# Build with no cache (critical!)
docker build --no-cache -f Dockerfile.fixed -t orac-stt:fixed .

# Verify dependencies installed
docker run --rm orac-stt:fixed python3.10 -c "import uvicorn, fastapi; print('OK')"

# Run with proper mounts
docker run -d --name orac-stt --runtime nvidia \
  -v /home/toby/orac-stt/third_party/whisper_cpp/models:/app/models:ro \
  -v /home/toby/orac-stt/third_party/whisper_cpp/bin:/app/third_party/whisper_cpp/bin:ro \
  -v /home/toby/orac-stt/third_party/whisper_cpp/lib:/app/third_party/whisper_cpp/lib:ro \
  -p 7272:7272 orac-stt:fixed
```

### Lesson Learned
When Docker builds show `CACHED` for critical steps but the container fails with missing dependencies, the cache is likely corrupted and needs `--no-cache` to force a complete rebuild. Always verify dependencies are actually installed before deployment.