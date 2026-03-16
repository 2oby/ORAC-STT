# ORAC STT — Next Steps

**Last Updated:** 2026-03-16
**Status:** Running, healthy, Whisper on CUDA, heartbeats flowing to Core

---

## Next Up

### 1. Sprint 1: Fix Whisper Binary Deployment
**Status:** Ready to implement
**Priority:** HIGH — Blocking clean deployments
**Documentation:** `docs/PHASE_3_IMPLEMENTATION_PROMPT.md` (historical context)

**Problem:** Container fails on fresh deployment with "Whisper binary not found at /app/models/whisper_cpp/whisper_cpp/bin/whisper-cli" because binary path doesn't survive Docker rebuilds.

**Tasks:**
- [ ] Apply immediate fix to current deployment (manual copy — done via quick fix)
- [ ] Update Dockerfile or entrypoint.sh to handle binary setup automatically
- [ ] Test deployment from clean state (remove container + image, rebuild)
- [ ] Document permanent solution

**Quick fix (current workaround):**
```bash
ssh orin4 "cd /home/toby/orac-stt && cp third_party/whisper_cpp/bin/whisper-cli models/whisper_cpp/whisper_cpp/bin/"
docker restart orac-stt
```

---

## Completed (2026-03-16)

- ~~**Docker cleanup cron on Orin**~~ — Weekly `docker image prune` cron installed for user `toby`.
- ~~**Project docs bootstrap**~~ — Created CLAUDE.md + NEXT.md matching OpenClaw/VPS structure.
