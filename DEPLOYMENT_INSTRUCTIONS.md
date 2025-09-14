# ORAC STT Fix Deployment Instructions

## Problem Summary
The ORAC STT Docker container won't start due to missing Python dependencies (uvicorn, fastapi, etc.) despite multiple rebuild attempts. The issue is caused by Docker cache corruption and improper dependency installation.

## Solution Files Created
1. **Dockerfile.fixed** - Clean Dockerfile that properly installs all Python dependencies
2. **docker-compose.fixed.yml** - Updated compose file that mounts whisper.cpp from host
3. **scripts/fix_orac_stt.sh** - Automated deployment script

## Manual Deployment Steps (when connected to Orin network)

### Option 1: Use the automated script
```bash
cd "/Users/2oby/pCloud Box/Projects/ORAC/ORAC STT"
./scripts/fix_orac_stt.sh
```

### Option 2: Manual deployment

1. **Copy files to Orin:**
```bash
scp Dockerfile.fixed toby@orin4:/home/toby/orac-stt/
scp docker-compose.fixed.yml toby@orin4:/home/toby/orac-stt/
rsync -avz src/ requirements.txt config.toml.example toby@orin4:/home/toby/orac-stt/
```

2. **SSH to Orin:**
```bash
ssh toby@orin4
cd /home/toby/orac-stt
```

3. **Stop and remove old container:**
```bash
docker stop orac-stt
docker rm orac-stt
```

4. **Build new image with --no-cache (CRITICAL):**
```bash
docker build --no-cache -f Dockerfile.fixed -t orac-stt:fixed .
```

5. **Verify dependencies are installed:**
```bash
docker run --rm orac-stt:fixed python3.10 -c "import uvicorn, fastapi; print('OK')"
```

6. **Start container:**
```bash
docker-compose -f docker-compose.fixed.yml up -d
```

7. **Check status:**
```bash
docker ps | grep orac-stt
docker logs --tail 50 orac-stt
curl http://localhost:7272/health
```

## Key Changes Made

### Dockerfile.fixed
- Uses `python3.10 -m pip install` explicitly
- Installs pip packages in smaller groups to ensure proper installation
- Adds verification steps to confirm uvicorn/fastapi are installed
- Sets PYTHONUNBUFFERED=1 for proper output
- Uses full path `/usr/bin/python3.10` in CMD
- Does NOT build whisper.cpp (mounts from host instead)

### docker-compose.fixed.yml
- Mounts whisper.cpp from host: `/home/toby/orac-stt/third_party/whisper_cpp/`
- Sets LD_LIBRARY_PATH for whisper.cpp libraries
- Uses Dockerfile.fixed for building

## Verification
After deployment, the container should:
1. Start without ModuleNotFoundError
2. Respond to health checks at http://orin4:7272/health
3. Show "Dependencies OK" when testing imports
4. Mount whisper.cpp binaries from host correctly

## Troubleshooting
If the container still fails:
1. Check Docker build output for pip installation errors
2. Verify whisper.cpp files exist at `/home/toby/orac-stt/third_party/whisper_cpp/`
3. Run `docker run -it orac-stt:fixed bash` to debug interactively
4. Check if python3.10 can import modules: `python3.10 -c "import uvicorn"`

## Next Steps After Fix
Once ORAC STT is running, investigate the wake word detection issue:
- Check if HeyORAC speech_recorder thread is stuck
- Verify communication between HeyORAC and ORAC STT
- Test direct API calls to ORAC STT