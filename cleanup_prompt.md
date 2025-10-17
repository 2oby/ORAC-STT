# ORAC STT Cleanup Prompt

**Context:** This prompt is designed to guide AI assistants (like Claude) through the systematic cleanup of the ORAC STT codebase based on the technical debt analysis in `cleanup.md`.

---

## Project Context

ORAC STT is a Speech-to-Text service for NVIDIA Orin Nano that:
- Accepts audio streams from Hey ORAC (wake word detection)
- Transcribes using whisper.cpp (default) or PyTorch Whisper (optional)
- Forwards transcriptions to ORAC Core for AI processing
- Provides a web admin interface for monitoring
- Supports multiple topics for routing different wake words

**Current Status:** Phase 1 complete, working in production, but has technical debt from rapid prototyping.

**Key Files:**
- Main entry: `src/orac_stt/main.py`
- STT endpoint: `src/orac_stt/api/stt.py`
- Admin interface: `src/orac_stt/api/admin.py`
- Model loading: `src/orac_stt/models/unified_loader.py`
- Integration: `src/orac_stt/integrations/orac_core_client.py`

---

## Cleanup Goals

1. **Maintain Functionality** - All existing features must continue to work
2. **Improve Testability** - Enable comprehensive test coverage
3. **Reduce Technical Debt** - Remove duplicates, unused code, and poor patterns
4. **Enhance Maintainability** - Clear structure, consistent patterns, good documentation
5. **No Breaking Changes** - API contracts must remain stable

---

## Phase 1: Foundation (Priority: URGENT)

**Estimated Time:** 1-2 days
**Risk Level:** LOW
**Dependencies:** None

### Task 1.1: Consolidate Docker Files
**Goal:** Merge duplicate Dockerfiles into single canonical version

**Files to Modify:**
- `Dockerfile` (keep and enhance)
- `Dockerfile.fixed` (merge improvements, then delete)
- `docker-compose.yml` (keep and fix)
- `docker-compose.fixed.yml` (delete)

**Steps:**
1. Compare `Dockerfile` and `Dockerfile.fixed`
2. Merge best practices from both:
   - Keep explicit python3.10 commands from .fixed
   - Keep verification steps from .fixed
   - Keep LD_LIBRARY_PATH setup from .fixed
   - Keep PYTHONUNBUFFERED from .fixed
3. Fix duplicate environment: blocks in docker-compose.yml
4. Test build: `docker build -t orac-stt:test .`
5. Test run: `docker-compose up -d`
6. Verify health: `curl http://localhost:7272/health`
7. Delete `Dockerfile.fixed` and `docker-compose.fixed.yml`
8. Update `DEPLOYMENT_INSTRUCTIONS.md` if needed

**Acceptance Criteria:**
- [ ] Single Dockerfile builds successfully
- [ ] Container starts and passes health check
- [ ] All volume mounts work correctly
- [ ] No duplicate docker-compose files

**Git Commit Message:**
```
chore: consolidate Docker configuration

- Merge Dockerfile.fixed improvements into main Dockerfile
- Remove duplicate docker-compose.fixed.yml
- Fix duplicate environment blocks in docker-compose.yml
- Add comments explaining key decisions
```

---

### Task 1.2: Split Requirements Files
**Goal:** Separate production, development, and optional dependencies

**Files to Create:**
- `requirements.txt` (production only)
- `requirements-dev.txt` (testing, linting)
- `requirements-pytorch.txt` (optional PyTorch backend)

**Current requirements.txt breakdown:**
```
Lines 1-10:  Core web framework (keep in requirements.txt)
Lines 11-13: Config (keep)
Lines 14:    Metrics (keep)
Lines 16-19: Audio processing (keep)
Lines 21-24: PyTorch (move to requirements-pytorch.txt)
Lines 26-29: HTTP client (keep, remove comments)
Lines 31-38: Development tools (move to requirements-dev.txt)
```

**Steps:**
1. Create `requirements-dev.txt`:
   ```
   # Development and Testing
   pytest==7.4.3
   pytest-asyncio==0.21.1
   pytest-cov==4.1.0
   black==23.11.0
   isort==5.12.0
   mypy==1.7.1
   flake8==6.1.0

   # Include production dependencies
   -r requirements.txt
   ```

2. Create `requirements-pytorch.txt`:
   ```
   # Optional PyTorch backend for Whisper
   # Only needed if USE_WHISPER_CPP=false
   torch==2.1.0
   torchaudio==2.1.0
   openai-whisper==20231117

   # Include core dependencies
   -r requirements.txt
   ```

3. Update `requirements.txt`:
   - Remove lines 21-24 (PyTorch)
   - Remove lines 31-38 (dev tools)
   - Remove commented lines 28-29 (httpx, tenacity)
   - Keep only production dependencies

4. Update `Dockerfile`:
   ```dockerfile
   # Install Python dependencies - Core only
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Note: PyTorch dependencies (requirements-pytorch.txt) are NOT installed
   # by default. whisper.cpp is used instead for better performance.
   ```

5. Update `.github/workflows/` (if exists) to use requirements-dev.txt
6. Update documentation to explain new structure
7. Test installation: `pip install -r requirements.txt`

**Acceptance Criteria:**
- [ ] Three separate requirements files exist
- [ ] Production requirements.txt has no dev dependencies
- [ ] Dev requirements includes production via -r
- [ ] Docker build succeeds with new requirements.txt
- [ ] Documentation updated

**Git Commit Message:**
```
refactor: split requirements into production/dev/optional

- Move dev tools to requirements-dev.txt
- Move PyTorch to requirements-pytorch.txt (optional)
- Remove commented dependencies (httpx, tenacity)
- Update Dockerfile to use production requirements only
- Update documentation with new dependency structure

Breaking: Developers must now use `pip install -r requirements-dev.txt`
```

---

### Task 1.3: Remove Unused Files
**Goal:** Delete files that serve no purpose

**Files to Delete:**
1. `test_whisper_fix.py` (root level) - move to tests/ first if keeping
2. `scripts/generate_certs.sh` (empty placeholder)
3. `Dockerfile.fixed` (after Task 1.1)
4. `docker-compose.fixed.yml` (after Task 1.1)

**Steps:**
1. Check git history to understand why files were created
2. For `test_whisper_fix.py`:
   - If useful, move to `tests/manual/test_whisper_fix.py`
   - If not, delete entirely
3. Delete `scripts/generate_certs.sh` or implement it properly
4. Update any scripts that reference deleted files
5. Update .gitignore if needed

**Acceptance Criteria:**
- [ ] No references to deleted files in codebase
- [ ] Git history preserved (files deleted, not removed from history)
- [ ] Scripts still work

**Git Commit Message:**
```
chore: remove unused and duplicate files

- Delete test_whisper_fix.py (superseded by test suite)
- Delete scripts/generate_certs.sh (empty placeholder)
- Remove duplicate Docker files (consolidated in previous commit)
```

---

### Task 1.4: Create Test Structure
**Goal:** Establish foundation for comprehensive testing

**Directories to Create:**
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_audio_processor.py
│   ├── test_audio_validator.py
│   ├── test_command_buffer.py
│   └── test_config_loader.py
├── integration/
│   ├── __init__.py
│   ├── test_stt_endpoint.py
│   └── test_health_endpoint.py
├── fixtures/
│   ├── audio_samples/
│   │   ├── silence_1s.wav
│   │   ├── speech_3s.wav
│   │   └── invalid.txt
│   └── config/
│       └── test_config.toml
└── README.md                # Test documentation
```

**Steps:**
1. Create directory structure
2. Create `tests/conftest.py` with basic fixtures:
   ```python
   import pytest
   from pathlib import Path
   from fastapi.testclient import TestClient

   @pytest.fixture
   def test_audio_dir():
       return Path(__file__).parent / "fixtures" / "audio_samples"

   @pytest.fixture
   def test_client():
       from orac_stt.main import create_app
       app = create_app()
       return TestClient(app)
   ```

3. Create `tests/unit/test_command_buffer.py`:
   ```python
   import pytest
   from orac_stt.history.command_buffer import CommandBuffer

   def test_command_buffer_initialization():
       buffer = CommandBuffer(max_size=3)
       assert buffer.max_size == 3
       assert len(buffer.get_commands()) == 0

   def test_add_command():
       buffer = CommandBuffer(max_size=3)
       buffer.add_command(
           text="test command",
           duration=1.0,
           confidence=0.95
       )
       commands = buffer.get_commands()
       assert len(commands) == 1
       assert commands[0].text == "test command"

   def test_circular_buffer():
       buffer = CommandBuffer(max_size=2)
       buffer.add_command(text="cmd1", duration=1.0, confidence=0.9)
       buffer.add_command(text="cmd2", duration=1.0, confidence=0.9)
       buffer.add_command(text="cmd3", duration=1.0, confidence=0.9)

       commands = buffer.get_commands()
       assert len(commands) == 2
       assert commands[0].text == "cmd2"
       assert commands[1].text == "cmd3"
   ```

4. Create `tests/integration/test_health_endpoint.py`:
   ```python
   def test_health_endpoint(test_client):
       response = test_client.get("/health")
       assert response.status_code == 200
       data = response.json()
       assert data["status"] in ["healthy", "initializing"]
   ```

5. Create `tests/README.md` explaining test structure
6. Generate test audio files (silence, speech samples)
7. Run tests: `pytest tests/ -v`

**Acceptance Criteria:**
- [ ] Test directory structure created
- [ ] At least 3 unit tests passing
- [ ] At least 1 integration test passing
- [ ] pytest runs successfully
- [ ] Test documentation exists

**Git Commit Message:**
```
test: establish test structure and foundation

- Create tests/ directory with unit/integration structure
- Add conftest.py with shared fixtures
- Add initial CommandBuffer unit tests
- Add health endpoint integration test
- Add test documentation and audio fixtures
```

---

### Task 1.5: Add CI Pipeline
**Goal:** Automate testing on every commit

**File to Create:**
`.github/workflows/test.yml`

**Content:**
```yaml
name: Test

on:
  push:
    branches: [ master, main, develop ]
  pull_request:
    branches: [ master, main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python 3.10
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y libsndfile1 ffmpeg

    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt

    - name: Run linters
      run: |
        black --check src/
        isort --check-only src/
        flake8 src/ --max-line-length=100

    - name: Run type checker
      run: |
        mypy src/orac_stt/ --ignore-missing-imports

    - name: Run tests
      run: |
        pytest tests/ -v --cov=src/orac_stt --cov-report=term-missing

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      if: always()
```

**Steps:**
1. Create `.github/workflows/` directory
2. Add `test.yml` with above content
3. Adjust paths if needed
4. Test locally with `act` tool (optional)
5. Push and verify workflow runs
6. Add status badge to README.md

**Acceptance Criteria:**
- [ ] Workflow file exists
- [ ] Workflow runs on push to master
- [ ] Tests pass in CI
- [ ] Coverage report generated
- [ ] Badge added to README

**Git Commit Message:**
```
ci: add GitHub Actions workflow for testing

- Add test workflow for PR and push to master
- Run linters (black, isort, flake8)
- Run type checker (mypy)
- Run pytest with coverage
- Upload coverage to codecov
```

---

## Phase 2: Code Quality (Priority: HIGH)

**Estimated Time:** 3-4 days
**Risk Level:** MEDIUM
**Dependencies:** Phase 1 complete

### Task 2.1: Refactor Global Singletons
**Goal:** Replace global singleton pattern with dependency injection

**Files to Modify:**
- `src/orac_stt/api/stt.py`
- `src/orac_stt/integrations/orac_core_client.py`
- `src/orac_stt/core/heartbeat_manager.py`

**Current Pattern (BEFORE):**
```python
# api/stt.py
_model_loader: Optional[UnifiedWhisperLoader] = None

def get_model_loader() -> UnifiedWhisperLoader:
    global _model_loader
    if _model_loader is None:
        settings = load_config()
        _model_loader = UnifiedWhisperLoader(settings.model)
    return _model_loader
```

**New Pattern (AFTER):**
```python
# api/stt.py
from functools import lru_cache
from fastapi import Depends

@lru_cache(maxsize=1)
def get_model_loader(
    settings: Settings = Depends(get_settings)
) -> UnifiedWhisperLoader:
    """Get or create model loader (cached singleton)."""
    return UnifiedWhisperLoader(settings.model)

@router.post("/stream/{topic}")
async def transcribe_stream_with_topic(
    topic: str,
    file: UploadFile = File(...),
    model_loader: UnifiedWhisperLoader = Depends(get_model_loader),
    command_buffer: CommandBuffer = Depends(get_command_buffer),
    core_client: ORACCoreClient = Depends(get_core_client)
):
    # Use injected dependencies
    ...
```

**Steps:**
1. Create `src/orac_stt/dependencies.py`:
   ```python
   """FastAPI dependency injection providers."""
   from functools import lru_cache
   from fastapi import Depends

   from .config.loader import load_config
   from .config.settings import Settings
   from .models.unified_loader import UnifiedWhisperLoader
   from .history.command_buffer import CommandBuffer
   from .integrations.orac_core_client import ORACCoreClient

   @lru_cache(maxsize=1)
   def get_settings() -> Settings:
       return load_config()

   @lru_cache(maxsize=1)
   def get_model_loader(settings: Settings = Depends(get_settings)) -> UnifiedWhisperLoader:
       return UnifiedWhisperLoader(settings.model)

   @lru_cache(maxsize=1)
   def get_command_buffer() -> CommandBuffer:
       return CommandBuffer(max_size=5)

   @lru_cache(maxsize=1)
   def get_core_client(settings: Settings = Depends(get_settings)) -> ORACCoreClient:
       core_url = getattr(settings, 'orac_core_url', 'http://192.168.8.192:8000')
       return ORACCoreClient(base_url=core_url)
   ```

2. Update `api/stt.py`:
   - Remove global variables
   - Remove `get_*` functions
   - Import from dependencies.py
   - Add `Depends()` to endpoint parameters

3. Update `api/admin.py`:
   - Import from dependencies.py
   - Update endpoints to use Depends()

4. Update tests to inject mock dependencies
5. Test all endpoints still work
6. Verify no race conditions

**Acceptance Criteria:**
- [ ] No global singletons in api/stt.py
- [ ] All dependencies use FastAPI Depends()
- [ ] Tests pass with injected mocks
- [ ] No race conditions in concurrent requests
- [ ] Documentation updated

**Git Commit Message:**
```
refactor: replace global singletons with dependency injection

- Create dependencies.py with FastAPI dependency providers
- Replace global _model_loader with Depends(get_model_loader)
- Replace global _command_buffer with Depends(get_command_buffer)
- Replace global _core_client with Depends(get_core_client)
- Update all endpoints to use dependency injection
- Update tests to inject mocks

Benefits:
- Better testability with mock injection
- Explicit dependencies in function signatures
- Thread-safe with lru_cache
- Easier to understand data flow
```

---

### Task 2.2: Refactor Monolithic STT Function
**Goal:** Break down `_transcribe_impl()` into testable components

**File to Modify:**
- `src/orac_stt/api/stt.py:230-386` (157 lines)

**Current Issues:**
- Single function does 8 different things
- Hard to test individual steps
- Complex error handling intertwined with logic
- Multiple levels of nesting

**New Structure:**
```python
# api/stt.py (refactored)

async def _transcribe_impl(...):
    """Main transcription orchestrator."""
    start_time = time.time()

    try:
        # 1. Load and validate audio
        audio_data, sample_rate, duration = await load_and_validate_audio(file)

        # 2. Save debug recording if enabled
        audio_path = await save_debug_recording_if_enabled(
            audio_data, sample_rate, "[Processing...]"
        )

        # 3. Transcribe with error handling
        result = await transcribe_with_error_handling(
            audio_data, sample_rate, language, task, model_loader
        )

        # 4. Add to command history
        await add_to_command_history(
            text=result.text,
            audio_path=audio_path,
            duration=duration,
            confidence=result.confidence,
            processing_time=time.time() - start_time,
            language=result.language,
            has_error=result.has_error,
            command_buffer=command_buffer
        )

        # 5. Forward to ORAC Core if successful
        if not result.has_error and forward_to_core:
            await forward_to_core_async(
                text=result.text,
                topic=topic,
                metadata=result.metadata,
                core_client=core_client
            )

        # 6. Build response
        return build_transcription_response(result, duration, time.time() - start_time)

    except AudioValidationError as e:
        return handle_validation_error(e, command_buffer)
    except Exception as e:
        return handle_unexpected_error(e, command_buffer)
```

**Steps:**
1. Create new functions in `api/stt.py` or separate module `api/stt_handlers.py`:
   - `async def load_and_validate_audio(file: UploadFile) -> tuple[np.ndarray, int, float]`
   - `async def save_debug_recording_if_enabled(...) -> Optional[Path]`
   - `async def transcribe_with_error_handling(...) -> TranscriptionResult`
   - `async def add_to_command_history(...) -> None`
   - `async def forward_to_core_async(...) -> None`
   - `def build_transcription_response(...) -> TranscriptionResponse`

2. Create `TranscriptionResult` dataclass to hold intermediate results
3. Extract each section of current `_transcribe_impl()` into functions
4. Update `_transcribe_impl()` to orchestrate the steps
5. Add unit tests for each new function
6. Integration test for full flow
7. Verify error handling still works correctly

**Acceptance Criteria:**
- [ ] Each step is a separate, testable function
- [ ] Main function is < 50 lines
- [ ] Each helper function has unit test
- [ ] Integration test covers full flow
- [ ] Error handling behavior unchanged
- [ ] All existing tests still pass

**Git Commit Message:**
```
refactor: decompose monolithic transcription function

- Extract load_and_validate_audio() for audio processing
- Extract save_debug_recording_if_enabled() for debug saves
- Extract transcribe_with_error_handling() for ML inference
- Extract add_to_command_history() for history management
- Extract forward_to_core_async() for Core integration
- Add TranscriptionResult dataclass for intermediate state
- Add unit tests for each extracted function

Reduces _transcribe_impl from 157 lines to ~40 lines
Each step now independently testable
```

---

### Task 2.3: Implement Custom Exception Hierarchy
**Goal:** Replace broad exception catching with specific errors

**File to Create:**
- `src/orac_stt/exceptions.py`

**Content:**
```python
"""Custom exceptions for ORAC STT."""

class ORACSTTError(Exception):
    """Base exception for ORAC STT errors."""
    pass


class AudioError(ORACSTTError):
    """Base class for audio-related errors."""
    pass


class AudioValidationError(AudioError):
    """Audio validation failed (already exists in audio/validator.py)."""
    pass


class AudioLoadError(AudioError):
    """Failed to load audio file."""
    pass


class TranscriptionError(ORACSTTError):
    """Base class for transcription errors."""
    pass


class ModelLoadError(TranscriptionError):
    """Failed to load ML model."""
    pass


class ModelInferenceError(TranscriptionError):
    """Model inference failed."""
    pass


class IntegrationError(ORACSTTError):
    """Base class for integration errors."""
    pass


class ORACCoreConnectionError(IntegrationError):
    """Failed to connect to ORAC Core."""
    pass


class ORACCoreTimeoutError(IntegrationError):
    """ORAC Core request timed out."""
    pass


class ConfigurationError(ORACSTTError):
    """Configuration validation failed."""
    pass
```

**Steps:**
1. Create `exceptions.py` with hierarchy
2. Update `audio/validator.py` to move `AudioValidationError` to exceptions.py
3. Update `models/unified_loader.py`:
   - Catch specific exceptions during load
   - Raise `ModelLoadError` with context
4. Update `models/whisper_cpp.py`:
   - Raise `ModelInferenceError` on transcription failure
5. Update `integrations/orac_core_client.py`:
   - Raise `ORACCoreConnectionError` instead of returning None
   - Raise `ORACCoreTimeoutError` on timeout
6. Add global exception handler in `main.py`:
   ```python
   @app.exception_handler(ORACSTTError)
   async def orac_error_handler(request, exc):
       return JSONResponse(
           status_code=500,
           content={
               "error": exc.__class__.__name__,
               "message": str(exc),
               "type": "orac_stt_error"
           }
       )
   ```
7. Update error handling in `api/stt.py` to catch specific exceptions
8. Update tests to expect specific exceptions

**Acceptance Criteria:**
- [ ] Exception hierarchy defined
- [ ] All modules raise specific exceptions
- [ ] Global error handler returns consistent format
- [ ] Tests verify specific exception types
- [ ] Logging includes exception context

**Git Commit Message:**
```
feat: add custom exception hierarchy

- Create exceptions.py with ORAC STT exception types
- Replace broad Exception catching with specific types
- Add ModelLoadError for model initialization failures
- Add ModelInferenceError for transcription failures
- Add ORACCoreConnectionError for integration failures
- Add global exception handler for consistent error responses
- Update all modules to raise/catch specific exceptions

Improves error clarity and debugging
```

---

### Task 2.4: Remove or Archive Unused Code
**Goal:** Delete code that's never executed

**Files to Handle:**

1. **`src/orac_stt/models/whisper_model.py`** (134 lines)
   - PyTorch implementation never imported
   - Options:
     - A) Delete entirely if PyTorch backend not planned
     - B) Move to `archived/whisper_model.py` for reference
     - C) Keep but add tests and make it accessible

   **Recommendation: B) Archive it**

2. **`src/orac_stt/core/shutdown.py`** (50 lines)
   - Imported but ShutdownHandler never instantiated
   - Options:
     - A) Implement proper shutdown (use the class)
     - B) Delete and use FastAPI lifespan only

   **Recommendation: A) Implement it properly**

**Steps for whisper_model.py:**
1. Create `archived/` directory
2. Move `whisper_model.py` to `archived/models/whisper_model.py`
3. Add `archived/README.md`:
   ```markdown
   # Archived Code

   This directory contains code that's not currently used but kept for reference.

   ## whisper_model.py
   PyTorch backend implementation for Whisper. Not used because whisper.cpp
   provides better performance on Jetson. Keep as reference if PyTorch backend
   needed in future.
   ```
4. Remove from main codebase
5. Add note in `requirements-pytorch.txt` about archived implementation

**Steps for shutdown.py:**
1. Update `main.py` lifespan to use ShutdownHandler:
   ```python
   from .core.shutdown import shutdown_handler

   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # Startup
       logger.info("Starting ORAC STT Service")
       setup_command_observer()

       yield

       # Shutdown
       logger.info("Shutting down ORAC STT Service")
       await shutdown_handler.cleanup()

       # Close HTTP sessions
       from .integrations.orac_core_client import get_orac_core_client
       client = get_orac_core_client()
       await client.close()
   ```
2. Test shutdown: `docker stop orac-stt` should log cleanup messages
3. Verify no errors in logs

**Acceptance Criteria:**
- [ ] whisper_model.py moved to archived/ with README
- [ ] shutdown_handler properly implemented
- [ ] Graceful shutdown tested
- [ ] No unused imports remain

**Git Commit Message:**
```
chore: archive unused PyTorch implementation and fix shutdown

- Move whisper_model.py to archived/models/ for reference
- Implement proper shutdown handling with ShutdownHandler
- Close aiohttp sessions on shutdown
- Add cleanup logging
- Add archived/README.md explaining archived code

Reduces maintenance burden while preserving reference code
```

---

### Task 2.5: Consolidate Documentation
**Goal:** Reduce documentation files from 12 to ~5 core docs

**Current Structure (12 files):**
```
README.md
CLAUDE.md
CURRENT_FOCUS.md
API_REFERENCE.md
DEPLOYMENT_INSTRUCTIONS.md
DEVLOG.md
HEY_ORAC_solvedproblems.md
ORAC_STT_SOLVED_ISSUES.md
DONE_SPRINT_1_FIX_WHISPER_BINARY_2025-09-21.md
docs/ORAC_INTEGRATION_FLOW.md
docs/PHASE_3_IMPLEMENTATION_PROMPT.md
Documents/ORAC_STT_Requirements.md
```

**New Structure (5 files + archive):**
```
README.md                    # Overview, quick start, links
CHANGELOG.md                 # Version history (new)
docs/
  architecture.md            # System design + integration flow
  api.md                     # API reference
  deployment.md              # Deployment guide
  development.md             # Dev guide (from CLAUDE.md)
archive_docs/
  SPRINT_1_2025-09-21.md     # Sprint completion notes
  SOLVED_ISSUES_HISTORICAL.md # Merged solved issues
  DEVLOG.md                  # Historical dev log
  PHASE_3_PROMPT.md          # Old implementation prompt
```

**Steps:**
1. Create `docs/architecture.md`:
   - Merge content from `docs/ORAC_INTEGRATION_FLOW.md`
   - Add system design overview
   - Add component diagrams
   - Keep CURRENT_FOCUS.md separate (living document)

2. Rename and consolidate:
   - `API_REFERENCE.md` → `docs/api.md`
   - `DEPLOYMENT_INSTRUCTIONS.md` → `docs/deployment.md`
   - `CLAUDE.md` → `docs/development.md`

3. Create `CHANGELOG.md`:
   ```markdown
   # Changelog

   ## [0.1.0] - 2025-09-21
   ### Added
   - Initial release with whisper.cpp support
   - Admin web interface
   - Topic-based routing
   - Heartbeat forwarding from Hey ORAC

   ### Fixed
   - Whisper binary path resolution (Sprint 1)
   - Topics display in admin interface
   ```

4. Archive old docs:
   ```bash
   mkdir -p archive_docs
   mv DONE_SPRINT_1_*.md archive_docs/SPRINT_1_2025-09-21.md
   mv DEVLOG.md archive_docs/
   mv docs/PHASE_3_IMPLEMENTATION_PROMPT.md archive_docs/
   ```

5. Merge solved issues:
   ```bash
   cat HEY_ORAC_solvedproblems.md ORAC_STT_SOLVED_ISSUES.md \
     > archive_docs/SOLVED_ISSUES_HISTORICAL.md
   rm HEY_ORAC_solvedproblems.md ORAC_STT_SOLVED_ISSUES.md
   ```

6. Update `README.md` with navigation:
   ```markdown
   ## Documentation

   - [Architecture](docs/architecture.md) - System design and integration
   - [API Reference](docs/api.md) - Complete API documentation
   - [Deployment](docs/deployment.md) - How to deploy to Orin Nano
   - [Development](docs/development.md) - Development guide and workflow
   - [Changelog](CHANGELOG.md) - Version history
   - [Current Focus](CURRENT_FOCUS.md) - Active development status
   ```

7. Create `docs/README.md` as table of contents
8. Update all cross-references between docs
9. Update CLAUDE.md references if moving to docs/development.md

**Acceptance Criteria:**
- [ ] 5 main documentation files
- [ ] Historical docs in archive_docs/
- [ ] README has clear navigation
- [ ] All internal links updated
- [ ] No broken references

**Git Commit Message:**
```
docs: consolidate documentation structure

- Merge integration flow into docs/architecture.md
- Move API_REFERENCE.md to docs/api.md
- Move DEPLOYMENT_INSTRUCTIONS.md to docs/deployment.md
- Rename CLAUDE.md to docs/development.md
- Create CHANGELOG.md for version history
- Archive sprint completion notes
- Archive historical solved issues
- Archive old implementation prompts
- Add navigation to README.md
- Create docs/README.md as table of contents

Reduces 12 doc files to 5 core docs + archive
```

---

## Phase 3: Production Readiness (Priority: MEDIUM)

**Estimated Time:** 4-5 days
**Risk Level:** LOW-MEDIUM
**Dependencies:** Phase 2 complete

### Task 3.1: Add Comprehensive Prometheus Metrics
### Task 3.2: Implement Request Rate Limiting
### Task 3.3: Add Request Tracing/Correlation IDs
### Task 3.4: Expand Test Coverage to 60%+
### Task 3.5: Add Deployment Health Checks

*(Full details available on request)*

---

## Phase 4: Optional Enhancements (Priority: LOW)

### Task 4.1: Implement TLS/mTLS Properly
### Task 4.2: Add PyTorch Backend Tests
### Task 4.3: Multi-Instance Support
### Task 4.4: Performance Benchmarking Suite

*(Full details available on request)*

---

## Testing Strategy for All Changes

### Before Making Changes
1. Run existing tests: `pytest tests/ -v`
2. Verify service health: `curl http://localhost:7272/health`
3. Check container logs: `docker logs orac-stt`

### After Making Changes
1. Run tests: `pytest tests/ -v --cov`
2. Build Docker: `docker build -t orac-stt:test .`
3. Test deployment: `./scripts/deploy_and_test.sh`
4. Manual smoke test:
   ```bash
   # Health check
   curl http://localhost:7272/health

   # Metrics check
   curl http://localhost:7272/metrics | head -20

   # STT endpoint (with test audio)
   curl -X POST http://localhost:7272/stt/v1/stream \
     -F "file=@tests/fixtures/audio_samples/speech_3s.wav"

   # Admin interface
   open http://localhost:7272/admin/
   ```

### Regression Testing
For each phase, verify:
- [ ] Health endpoint returns 200
- [ ] Metrics endpoint returns data
- [ ] STT endpoint transcribes audio
- [ ] Admin interface loads
- [ ] WebSocket connects
- [ ] Topics load in admin UI
- [ ] Command history updates
- [ ] ORAC Core forwarding works (check logs)

---

## Git Workflow

### Branch Strategy
```bash
# Create feature branch
git checkout -b cleanup/phase-1-foundation

# Make changes for Task 1.1
git add Dockerfile docker-compose.yml
git commit -m "chore: consolidate Docker configuration"

# Make changes for Task 1.2
git add requirements*.txt
git commit -m "refactor: split requirements into production/dev/optional"

# Continue for all Phase 1 tasks...

# Push and create PR
git push origin cleanup/phase-1-foundation
gh pr create --title "Phase 1: Foundation cleanup" --body "See cleanup_prompt.md"
```

### Commit Message Format
```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change that neither fixes bug nor adds feature
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

---

## Rollback Plan

If any phase causes issues:

1. **Immediate Rollback:**
   ```bash
   git revert <commit-sha>
   ./scripts/deploy_and_test.sh
   ```

2. **Verify Service:**
   ```bash
   curl http://orin4:7272/health
   docker logs orac-stt --tail 50
   ```

3. **Investigation:**
   - Check logs for errors
   - Review test failures
   - Compare with cleanup.md analysis

4. **Re-attempt:**
   - Fix identified issues
   - Test locally first
   - Deploy incrementally

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Single Dockerfile builds and runs
- [ ] Three separate requirements files exist
- [ ] Unused files removed
- [ ] Test structure created with passing tests
- [ ] CI pipeline runs on every push
- [ ] All existing functionality still works

### Phase 2 Complete When:
- [ ] No global singletons, using dependency injection
- [ ] Main STT function < 50 lines
- [ ] Custom exception hierarchy in use
- [ ] Unused code archived
- [ ] Documentation consolidated to 5 core files
- [ ] Test coverage > 40%

### Phase 3 Complete When:
- [ ] Comprehensive Prometheus metrics
- [ ] Rate limiting implemented
- [ ] Request tracing added
- [ ] Test coverage > 60%
- [ ] Production deployment verified

---

## References

- **Technical Debt Analysis:** `cleanup.md`
- **Current Status:** `CURRENT_FOCUS.md`
- **Architecture:** `docs/ORAC_INTEGRATION_FLOW.md`
- **API Reference:** `API_REFERENCE.md`
- **Deployment:** `DEPLOYMENT_INSTRUCTIONS.md`

---

## Notes for AI Assistants

When executing this prompt:

1. **Read cleanup.md first** - Understand the full context
2. **One task at a time** - Don't try to do everything at once
3. **Test after each change** - Verify functionality preserved
4. **Ask for clarification** - If design decision unclear
5. **Document decisions** - Update CURRENT_FOCUS.md as you go
6. **Commit frequently** - Small, focused commits
7. **Preserve history** - Don't squash important commits
8. **Update this prompt** - If you find better approaches

**Remember:** The goal is to improve the codebase while maintaining 100% functionality. When in doubt, be conservative and ask the user.

---

**Last Updated:** 2025-10-17
**Version:** 1.0
**Status:** Ready for Phase 1
