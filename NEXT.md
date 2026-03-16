# ORAC STT - Next Session Agenda

## Priority Tasks

### 1. Sprint 1: Fix Whisper Binary Deployment
**Status**: Ready to implement
**Priority**: HIGH - Blocking clean deployments
**Documentation**: `docs/SPRINT_1_FIX_WHISPER_BINARY.md`

**Problem**: Container fails on fresh deployment with "Whisper binary not found" because binary path doesn't survive rebuilds.

**Tasks**:
- [ ] Apply immediate fix to current deployment
- [ ] Update Dockerfile or entrypoint to handle binary setup automatically
- [ ] Test deployment from clean state
- [ ] Document permanent solution

### 2. ~~Docker Cleanup Cron on Orin~~ DONE (2026-03-16)
- [x] Add weekly `docker image prune` cron for user `toby` on orin4
