# Sprint 1: Fix Whisper Binary Deployment Issue

## Problem
When redeploying ORAC STT on the Orin, the container fails with:
```
Error: Whisper binary not found at /app/models/whisper_cpp/whisper_cpp/bin/whisper-cli
```

This happens because the Whisper binary is built on the host but not properly mounted or available in the container.

## Root Cause
1. The Whisper binary is compiled on the host machine (Orin) at `/home/toby/orac-stt/models/whisper_cpp/`
2. The Docker container expects it at `/app/models/whisper_cpp/whisper_cpp/bin/whisper-cli`
3. The volume mount `-v /home/toby/orac-stt/models:/app/models` should handle this, but the binary is often missing or in the wrong location

## Solution

### Immediate Fix (Quick)
Before starting the container, ensure the Whisper binary exists on the host:

```bash
# On the Orin (via SSH)
cd /home/toby/orac-stt
mkdir -p models/whisper_cpp/whisper_cpp/bin/

# Build whisper.cpp if not already built
cd third_party/whisper_cpp
./build_whisper_cpp.sh

# Copy the binary to the expected location
cp build/bin/whisper-cli /home/toby/orac-stt/models/whisper_cpp/whisper_cpp/bin/

# Then restart the container
docker restart orac-stt
```

### Permanent Fix (Recommended)
Update the deployment script to always ensure the binary exists:

1. **Update `scripts/deploy_and_test.sh`** to include binary check:
```bash
# After pulling code, before building Docker image
echo "📦 Ensuring Whisper binary exists..."
ssh orin4 "cd /home/toby/orac-stt && \
    mkdir -p models/whisper_cpp/whisper_cpp/bin/ && \
    if [ ! -f models/whisper_cpp/whisper_cpp/bin/whisper-cli ]; then \
        echo 'Building Whisper binary...' && \
        cd third_party/whisper_cpp && \
        ./build_whisper_cpp.sh && \
        cp build/bin/whisper-cli ../../models/whisper_cpp/whisper_cpp/bin/ && \
        echo 'Whisper binary built and copied'; \
    else \
        echo 'Whisper binary already exists'; \
    fi"
```

2. **Alternative: Use Dockerfile.fixed** which doesn't require the binary:
```bash
docker build -t orac-stt:fixed -f Dockerfile.fixed .
docker run -d --name orac-stt ... orac-stt:fixed
```

## Testing
After applying the fix, verify:
```bash
# Check binary exists on host
ssh orin4 "ls -la /home/toby/orac-stt/models/whisper_cpp/whisper_cpp/bin/whisper-cli"

# Check container can access it
ssh orin4 "docker exec orac-stt ls -la /app/models/whisper_cpp/whisper_cpp/bin/whisper-cli"

# Test transcription
curl -X POST http://192.168.8.191:7272/stt/v1/transcribe \
  -F "audio=@test.wav" \
  -F "language=en"
```

## Success Criteria
- [ ] Container starts without Whisper binary errors
- [ ] Whisper binary persists across container restarts
- [ ] Deployment script handles binary setup automatically
- [ ] Transcription endpoint works correctly

## Implementation Time
- Immediate fix: 5 minutes
- Permanent fix: 15 minutes

## Notes
- The Whisper binary is architecture-specific (ARM64 for Orin)
- Cannot be built in Docker container due to missing CUDA libraries during build
- Must be built on host with proper CUDA environment
- Consider using `whisper.cpp` Python bindings as future improvement