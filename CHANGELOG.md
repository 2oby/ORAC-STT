# Changelog

All notable changes to the ORAC STT Service will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.3.0] - 2026-01-18

### Added
- Model restart functionality in admin UI (restart whisper-server with different model without container restart)
- Orange pulsing animation on restart button when selected model differs from running model
- `GET /admin/models/running` endpoint to get currently running model
- `POST /admin/models/restart` endpoint to restart whisper-server with new model
- Loading spinner animation on restart button during model switch

### Changed
- Upgraded default model from whisper-tiny to whisper-small for better accuracy
- Health endpoint now correctly reports "whisper-server" backend when using whisper.cpp server
- Fixed MODEL_NAME environment variable handling in pydantic settings

### Fixed
- Health endpoint was incorrectly reporting "pytorch" backend when using whisper-server
- Config TOML was overriding MODEL_NAME environment variable

---

## [0.2.0] - 2025-10-17

### Added
- Complete documentation restructure (README, USER_GUIDE, DEVELOPER_GUIDE, API_REFERENCE)
- Topic-based routing with lazy registration
- Heartbeat system for Hey ORAC integration
- Web admin dashboard with real-time command feed
- Audio playback in web dashboard
- Debug recordings system (circular buffer, last 5 recordings)
- Timezone-aware datetime handling (UTC with ISO format)
- Docker Compose v2 migration
- Split requirements files (core/dev/pytorch)

### Changed
- Refactored monolithic transcription function (157 → 73 lines)
- Extracted 9 specialized helper functions for better testability
- Migrated from `docker run` to `docker compose`
- Updated all documentation to use `docker compose` (space, not hyphen)
- Container timezone set to Europe/Zurich
- Improved error handling with dedicated error handlers

### Fixed
- Timezone display bug (heartbeat showing "2h ago")
- Changed `datetime.utcnow()` to `datetime.now(timezone.utc)` for timezone-aware datetimes
- Removed lru_cache from dependency functions to fix unhashable Settings error
- Docker Compose command syntax (v2 uses space, not hyphen)
- Timezone support with tzdata package installation

### Removed
- Global singletons (replaced with dependency injection)
- Duplicate docker-compose configuration blocks
- Obsolete documentation files (moved to docs/archive/)

---

## [0.1.0] - 2025-09-21

### Added
- Initial FastAPI implementation with STT endpoints
- whisper.cpp integration with CUDA support
- Command buffer with circular storage
- ORAC Core client integration
- Prometheus metrics endpoint
- Health check endpoints
- JSON structured logging
- TOML configuration with environment overrides
- Docker containerization for Orin Nano
- whisper.cpp build script for Jetson
- Basic web admin interface

### Fixed
- Whisper binary path and symlink handling
- Model loading and caching
- Audio format validation

---

## [Unreleased]

### Planned for 0.3.0
- Unit test coverage >80%
- WebSocket streaming transcription
- Batch processing endpoint
- Enhanced metrics dashboard
- CI/CD pipeline (GitHub Actions)

### Planned for 0.4.0
- Multiple model support (concurrent)
- Custom model upload
- Speaker diarization
- Word-level timestamps
- mTLS authentication

---

## Version History

| Version | Date       | Highlights |
|---------|------------|------------|
| 0.2.0   | 2025-10-17 | Documentation restructure, topic routing, heartbeat system, refactoring |
| 0.1.0   | 2025-09-21 | Initial release with whisper.cpp, Docker, web dashboard |

---

**Note**: For detailed information about each release, see the [GitHub Releases](https://github.com/2oby/ORAC-STT/releases) page.
