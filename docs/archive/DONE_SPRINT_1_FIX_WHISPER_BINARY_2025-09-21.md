# Sprint 1: Fix Whisper Binary Deployment Issue & Heartbeat System

## ✅ COMPLETED: 2025-09-21

## Problems Addressed

### 1. Whisper Binary Issue (✅ FIXED)
When redeploying ORAC STT on the Orin, the container was failing with:
```
Error: Whisper binary not found at /app/models/whisper_cpp/whisper_cpp/bin/whisper-cli
```

**Status:** FIXED - The deployment script now ensures the binary exists in the correct location.

### 2. Heartbeat Communication Issue (✅ FIXED)
The heartbeat system between Hey ORAC → ORAC STT → ORAC Core has issues:

**Current Status:**
- ✅ ORAC STT successfully forwards heartbeats to ORAC Core
- ✅ ORAC Core shows active topics (visible at http://192.168.8.192:8000)
- ✅ ORAC STT admin interface now shows topics (http://192.168.8.192:7272/admin/)
- ✅ Fixed datetime parsing issue in topic_registry.py

**Error Fixed:**
The error `"Failed to load topics: fromisoformat: argument must be str"` was caused by inconsistent datetime serialization in the YAML file. Fixed by:
1. Ensuring `save()` method explicitly converts datetime to ISO format strings
2. Adding type checking in `load()` method to handle both string and datetime objects
3. Topics now persist and load correctly across container restarts

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

## Debugging Steps for Heartbeat Issue

### Check Hey ORAC Configuration
1. **On Raspberry Pi (Hey ORAC):**
```bash
# Check what IP Hey ORAC is using for ORAC STT
docker exec hey-orac env | grep -i orac
# or check config file
docker exec hey-orac cat /app/config.yaml | grep -i stt
```

2. **Verify Network Path:**
- Hey ORAC (Pi) should connect to ORAC STT at: `http://192.168.8.192:7272`
- ORAC STT (Orin) should connect to ORAC Core at: `http://192.168.8.192:8000`

### Current Configuration Issues Found:
1. **IP Address Confusion:** System was using 192.168.8.191 instead of 192.168.8.192
2. **Docker Networking:** Containers on same host need proper addressing:
   - Initially tried `localhost:8000` - failed (different containers)
   - Then tried `172.18.0.2:8000` - failed (different networks)
   - Finally used `192.168.8.192:8000` - works

3. **Exception Handling Bug:**
   - Fixed `aiohttp.ClientTimeout` → `asyncio.TimeoutError`
   - Fixed bare `except:` → `except Exception:`
   - Added missing `import asyncio`

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
- [x] Container starts without Whisper binary errors
- [x] Whisper binary persists across container restarts
- [x] Deployment script handles binary setup automatically
- [x] Transcription endpoint works correctly
- [x] Topics display correctly in admin interface
- [x] Datetime serialization/deserialization works properly

## Implementation Time
- Immediate fix: 5 minutes
- Permanent fix: 15 minutes

## Notes
- The Whisper binary is architecture-specific (ARM64 for Orin)
- Cannot be built in Docker container due to missing CUDA libraries during build
- Must be built on host with proper CUDA environment
- Consider using `whisper.cpp` Python bindings as future improvement