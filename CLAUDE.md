# ORAC STT - Project Context

## What is ORAC STT?

High-performance Speech-to-Text service for the ORAC system. Receives audio from Hey ORAC, transcribes using whisper.cpp with CUDA acceleration, and forwards text to ORAC Core.

## Deployment

- **Target**: NVIDIA Orin Nano (`ssh orin4` / 192.168.8.192)
- **Remote path**: `/home/toby/orac-stt/`
- **Container**: `orac-stt:latest` on port 7272
- **Runtime**: NVIDIA (GPU-accelerated)
- **Admin UI**: http://192.168.8.192:7272/admin/

## Tech Stack

- Python 3.10, FastAPI/Uvicorn
- whisper.cpp (whisper-server mode, model stays loaded in GPU memory)
- Whisper base model, CUDA-accelerated
- Docker with NVIDIA runtime on Jetson

## Key Paths

| Path | Purpose |
|------|---------|
| `src/orac_stt/` | Main application code |
| `src/orac_stt/api/stt.py` | STT API endpoints |
| `src/orac_stt/core/heartbeat_manager.py` | Heartbeat forwarding to Core |
| `src/orac_stt/models/whisper_server.py` | Whisper server integration |
| `third_party/whisper_cpp/` | whisper.cpp binaries and libs (built on host) |
| `models/` | Model files |
| `scripts/deploy_and_test.sh` | Deploy to Orin |

## Deploy

```bash
cd scripts
./deploy_and_test.sh "commit message"
```

## Known Issues

- **Whisper binary path**: Container expects binary at a path that doesn't survive rebuilds. Quick fix: `ssh orin4 "cd /home/toby/orac-stt && cp third_party/whisper_cpp/bin/whisper-cli models/whisper_cpp/whisper_cpp/bin/"`
- Sprint 1 addresses this permanently

## Rules

- This service handles transcription only - no backend management or command processing
- whisper.cpp binaries must be built on the Jetson host (ARM + CUDA), not in container
- Host CUDA libs are mounted into the container (Jetson SBSA workaround)
