# ORAC STT — Project Context

> **Human?** Read [README.md](README.md) instead for project overview.

## What This Is

High-performance Speech-to-Text service for the ORAC system. Receives audio from Hey ORAC, transcribes using whisper.cpp with CUDA acceleration on the Jetson, and forwards text to ORAC Core.

## Key Infrastructure

- **Target:** NVIDIA Orin Nano (`ssh orin4` / 192.168.8.192)
- **Remote path:** `/home/toby/orac-stt/`
- **Container:** `orac-stt:latest` on port 7272
- **Runtime:** NVIDIA (GPU-accelerated)
- **Admin UI:** http://192.168.8.192:7272/admin/
- **GitHub:** https://github.com/2oby/ORAC-STT

## Project Layout

```
ORAC STT/
├── src/orac_stt/                    # Main application code
│   ├── api/stt.py                   # STT API endpoints (stream, health)
│   ├── core/heartbeat_manager.py    # Heartbeat forwarding to Core
│   ├── core/whisper_manager.py      # Whisper server lifecycle
│   ├── models/whisper_server.py     # Whisper server integration
│   ├── history/command_buffer.py    # Command history
│   └── integrations/orac_core_client.py  # Core API client
├── third_party/whisper_cpp/         # whisper.cpp binaries + libs (built on host)
│   ├── bin/whisper-cli              # Whisper binary
│   ├── lib/                         # Shared libraries
│   └── models/                      # Whisper model files
├── scripts/deploy_and_test.sh       # Deploy to Orin
├── docker-compose.yml               # Service definition
├── Dockerfile                       # Container build
└── models/                          # Model storage
```

## Important Rules

- **This service handles transcription only** — no backend management or command processing.
- **whisper.cpp binaries must be built on the Jetson host** (ARM + CUDA), not in the container. They're mounted read-only.
- **Host CUDA libs are mounted into the container** (`/usr/local/cuda/targets/aarch64-linux/lib`). Container's SBSA libs don't work on Jetson.
- **Whisper server mode** (`USE_WHISPER_SERVER=true`): model stays loaded in GPU memory for fast inference. Server managed by whisper_manager with watchdog.
- **Container memory limit:** 2GB (1GB reserved).

## Deploying

```bash
cd scripts
./deploy_and_test.sh "commit message"  # Commits, pushes, pulls on Orin, rebuilds Docker
```

## Common Commands

```bash
# Check service
ssh orin4 "docker logs -f orac-stt"
ssh orin4 "docker ps | grep orac-stt"
curl http://192.168.8.192:7272/health

# Restart
ssh orin4 "docker restart orac-stt"

# Quick fix for Whisper binary issue (until Sprint 1 is done)
ssh orin4 "cd /home/toby/orac-stt && cp third_party/whisper_cpp/bin/whisper-cli models/whisper_cpp/whisper_cpp/bin/"
```

## Known Issues

- **Whisper binary path:** Container expects binary at a path that doesn't survive rebuilds. Sprint 1 addresses this permanently. Quick fix above.
