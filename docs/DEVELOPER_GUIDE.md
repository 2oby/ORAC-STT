# ORAC STT Developer Guide

Developer documentation for contributing to and extending the ORAC STT Service.

**Version:** 0.2.0 | **Last Updated:** October 17, 2025

---

## Table of Contents

1. [Project Architecture](#project-architecture)
2. [Development Setup](#development-setup)
3. [Code Structure](#code-structure)
4. [Development Workflow](#development-workflow)
5. [Testing](#testing)
6. [Code Quality](#code-quality)
7. [Contributing](#contributing)
8. [Release Process](#release-process)

---

## Project Architecture

### System Overview

```
src/orac_stt/
├── main.py                     # FastAPI application entry point
├── config/
│   └── settings.py             # Configuration management (TOML + env)
├── api/
│   ├── stt.py                  # STT endpoints (/stt/v1/stream, /heartbeat)
│   └── monitoring.py           # Health and metrics endpoints
├── core/
│   ├── heartbeat_manager.py    # Heartbeat processing and forwarding
│   └── topic_registry.py       # Topic registration and management
├── models/
│   ├── unified_loader.py       # whisper.cpp loader
│   ├── topic.py                # Topic data models
│   └── heartbeat.py            # Heartbeat data models
├── audio/
│   ├── processor.py            # Audio loading and processing
│   └── validator.py            # Audio format validation
├── history/
│   └── command_buffer.py       # Command history management
├── integrations/
│   └── orac_core_client.py     # ORAC Core HTTP client
├── utils/
│   └── logging.py              # Structured JSON logging
└── dependencies.py             # FastAPI dependency injection
```

### Key Design Patterns

**1. Dependency Injection**
- FastAPI `Depends()` for service injection
- Singleton instances managed via `dependencies.py`
- Testable by mocking dependencies

**2. Separation of Concerns**
- API layer (`api/`) - HTTP request/response
- Core layer (`core/`) - Business logic
- Models layer (`models/`) - Data and ML
- Integration layer (`integrations/`) - External services

**3. Configuration Management**
- TOML files for structured config
- Environment variable overrides with `ORAC_` prefix
- Pydantic models for validation

**4. Error Handling**
- Custom exceptions (`AudioValidationError`)
- Dedicated error handlers per layer
- Graceful degradation (failed transcriptions don't crash service)

---

## Development Setup

### Local Development Environment

**Requirements:**
- Python 3.10+
- Git
- Access to Orin Nano (for testing whisper.cpp)

**Setup:**

```bash
# Clone repository
git clone https://github.com/2oby/ORAC-STT.git
cd ORAC-STT

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy configuration template
cp config.toml.example config.toml

# Edit configuration for local development
nano config.toml
```

### Configuration for Local Development

```toml
[app]
log_level = "DEBUG"
environment = "development"

[api]
host = "127.0.0.1"  # Localhost only
port = 7272

[model]
name = "whisper-tiny"  # Faster for development
device = "cpu"  # Unless you have CUDA locally
```

### Running Locally (Without whisper.cpp)

For API development without ML:

```python
# Mock the model loader in dependencies.py
from unittest.mock import MagicMock

def get_model_loader():
    mock_loader = MagicMock()
    mock_loader.transcribe.return_value = {
        "text": "mock transcription",
        "confidence": 0.95,
        "language": "en"
    }
    return mock_loader
```

Then run:
```bash
python -m src.orac_stt.main
```

---

## Code Structure

### Adding a New Endpoint

**1. Define request/response models:**
```python
# src/orac_stt/api/stt.py
from pydantic import BaseModel

class MyRequest(BaseModel):
    param: str

class MyResponse(BaseModel):
    result: str
```

**2. Create endpoint:**
```python
@router.post("/my-endpoint", response_model=MyResponse)
async def my_endpoint(
    request: MyRequest,
    service: MyService = Depends(get_my_service)
) -> MyResponse:
    result = await service.process(request.param)
    return MyResponse(result=result)
```

**3. Register router:**
```python
# src/orac_stt/main.py
from .api.my_api import router as my_router
app.include_router(my_router, prefix="/api/v1", tags=["my-feature"])
```

### Adding Configuration

**1. Add to config.toml.example:**
```toml
[my_feature]
enabled = true
timeout = 30
```

**2. Add to Settings model:**
```python
# src/orac_stt/config/settings.py
class MyFeatureSettings(BaseModel):
    enabled: bool = True
    timeout: int = 30

class Settings(BaseModel):
    # ... existing settings ...
    my_feature: MyFeatureSettings = Field(default_factory=MyFeatureSettings)
```

**3. Use in code:**
```python
settings = get_settings()
if settings.my_feature.enabled:
    # Feature logic
    pass
```

### Adding a Model

**1. Create model class:**
```python
# src/orac_stt/models/my_model.py
from pydantic import BaseModel

class MyModel(BaseModel):
    id: str
    name: str
    created_at: datetime
```

**2. Add loader if needed:**
```python
class MyModelLoader:
    def __init__(self, config):
        self.config = config
        self._model = None

    def load_model(self):
        # Load model
        pass

    def predict(self, input_data):
        # Run inference
        pass
```

---

## Development Workflow

### Git Workflow

**Branches:**
- `main` - Production-ready code
- `cleanup/phase-1-foundation` - Current development branch
- Feature branches: `feature/your-feature-name`
- Bugfix branches: `fix/issue-description`

**Workflow:**

```bash
# 1. Create feature branch
git checkout -b feature/my-feature cleanup/phase-1-foundation

# 2. Make changes
# ... edit files ...

# 3. Test locally
pytest
black src/ tests/
mypy src/

# 4. Commit with descriptive message
git add .
git commit -m "feat: add new feature description"

# 5. Push to GitHub
git push origin feature/my-feature

# 6. Create Pull Request
gh pr create --base cleanup/phase-1-foundation --head feature/my-feature
```

### Commit Message Format

Follow conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code restructuring
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `chore:` - Maintenance tasks

**Examples:**
```
feat: add batch transcription endpoint
fix: resolve audio format validation bug
refactor: decompose monolithic transcription function
docs: update API reference with new endpoints
test: add unit tests for audio processor
chore: update dependencies to latest versions
```

### Deployment Workflow

**From Development Machine:**

```bash
# Deploy to Orin
cd scripts
./deploy_and_test.sh

# The script handles:
# 1. Git commit and push
# 2. Pull on Orin
# 3. whisper.cpp check
# 4. Docker build
# 5. Container restart
# 6. Health checks
```

---

## Testing

### Test Structure

```
tests/
├── unit/                  # Unit tests (fast, isolated)
│   ├── test_audio_processor.py
│   ├── test_stt_handlers.py
│   └── test_topic_registry.py
├── integration/           # Integration tests (slower, real services)
│   ├── test_api_endpoints.py
│   └── test_whisper_integration.py
└── fixtures/              # Test data and fixtures
    ├── audio_samples/
    └── conftest.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_audio_processor.py

# Run with coverage
pytest --cov=src/orac_stt --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run with verbose output
pytest -v

# Run tests matching pattern
pytest -k "test_audio"
```

### Writing Tests

**Unit Test Example:**

```python
# tests/unit/test_audio_processor.py
import pytest
from src.orac_stt.audio.processor import AudioProcessor
from src.orac_stt.audio.validator import AudioValidationError

def test_audio_processor_loads_valid_wav():
    processor = AudioProcessor()
    with open("tests/fixtures/audio_samples/valid.wav", "rb") as f:
        audio_data, sample_rate = processor.load_audio(f.read())

    assert sample_rate == 16000
    assert len(audio_data) > 0

def test_audio_processor_rejects_stereo():
    processor = AudioProcessor()
    with open("tests/fixtures/audio_samples/stereo.wav", "rb") as f:
        with pytest.raises(AudioValidationError, match="mono"):
            processor.load_audio(f.read())
```

**Integration Test Example:**

```python
# tests/integration/test_api_endpoints.py
from fastapi.testclient import TestClient
from src.orac_stt.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_transcribe_endpoint():
    with open("tests/fixtures/audio_samples/hello.wav", "rb") as f:
        response = client.post(
            "/stt/v1/stream/general",
            files={"file": f}
        )

    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert "confidence" in data
```

---

## Code Quality

### Code Formatting

**Black** (automatic formatting):
```bash
# Format all code
black src/ tests/

# Check what would be formatted
black --check src/ tests/
```

**Configuration** (pyproject.toml):
```toml
[tool.black]
line-length = 100
target-version = ['py310']
```

### Type Checking

**mypy** (static type checker):
```bash
# Check types
mypy src/

# Strict mode
mypy --strict src/
```

**Type hints example:**
```python
from typing import Optional, List, Dict, Any

async def transcribe_audio(
    audio_data: np.ndarray,
    sample_rate: int,
    model_loader: UnifiedWhisperLoader,
    language: Optional[str] = None
) -> Dict[str, Any]:
    # Implementation
    pass
```

### Linting

**flake8** (style checker):
```bash
# Run linter
flake8 src/ tests/

# Configuration in .flake8 or pyproject.toml
```

### Pre-commit Hooks

**Setup** (recommended):
```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

**Configuration** (.pre-commit-config.yaml):
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
```

---

## Contributing

### Pull Request Process

1. **Create feature branch** from `cleanup/phase-1-foundation`
2. **Implement changes** with tests
3. **Run quality checks**:
   ```bash
   pytest
   black src/ tests/
   mypy src/
   flake8 src/ tests/
   ```
4. **Update documentation** if needed
5. **Create Pull Request** with description
6. **Address review feedback**
7. **Merge** after approval

### Code Review Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Type hints present
- [ ] Error handling appropriate
- [ ] Logging added for debugging
- [ ] Performance considered
- [ ] Security implications reviewed
- [ ] Backward compatibility maintained

### Documentation Standards

- Docstrings for all public functions/classes
- Type hints for function signatures
- README updates for new features
- API reference updates for new endpoints
- User guide updates for user-facing changes

**Docstring Example:**
```python
async def transcribe_audio(
    audio_data: np.ndarray,
    sample_rate: int,
    model_loader: UnifiedWhisperLoader,
    language: Optional[str] = None,
    task: str = "transcribe"
) -> Dict[str, Any]:
    """Transcribe audio data using the model.

    Args:
        audio_data: Audio samples as numpy array
        sample_rate: Sample rate (must be 16000)
        model_loader: Model loader instance (injected)
        language: Optional language code (e.g., "en", "es")
        task: Task type - "transcribe" or "translate"

    Returns:
        Dictionary containing:
        - text (str): Transcribed text
        - confidence (float): Confidence score 0-1
        - language (str): Detected/specified language

    Raises:
        ModelLoadError: If model fails to load
        TranscriptionError: If transcription fails
    """
    # Implementation
```

---

## Release Process

### Version Numbering

Follow Semantic Versioning (SemVer):
- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

**Example**: `0.2.0` → `0.3.0` (new feature) → `0.3.1` (bug fix)

### Release Checklist

1. **Update version** in relevant files
2. **Update CHANGELOG.md** with changes
3. **Run full test suite**
4. **Update documentation**
5. **Create git tag**: `git tag v0.3.0`
6. **Push tag**: `git push origin v0.3.0`
7. **Create GitHub release** with notes
8. **Deploy to production** via deploy script

---

## Development Tips

### Debugging

**Enable debug logging:**
```bash
export ORAC_LOG_LEVEL=DEBUG
python -m src.orac_stt.main
```

**Use iPython for REPL:**
```bash
ipython
>>> from src.orac_stt.audio.processor import AudioProcessor
>>> processor = AudioProcessor()
>>> # Interactive debugging
```

**Docker debugging:**
```bash
# Access running container
docker compose exec orac-stt bash

# Check Python environment
docker compose exec orac-stt python3.10 -c "import sys; print(sys.path)"

# Run Python REPL in container
docker compose exec orac-stt python3.10
```

### Performance Profiling

**cProfile:**
```python
import cProfile
import pstats

cProfile.run('my_function()', 'profile_stats')
stats = pstats.Stats('profile_stats')
stats.sort_stats('cumulative')
stats.print_stats(20)
```

**Memory profiling:**
```python
from memory_profiler import profile

@profile
def my_function():
    # Function to profile
    pass
```

---

## Resources

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [whisper.cpp GitHub](https://github.com/ggerganov/whisper.cpp)

### Internal References
- [USER_GUIDE.md](./USER_GUIDE.md) - Deployment and usage
- [API_REFERENCE.md](./API_REFERENCE.md) - API documentation
- [../README.md](../README.md) - Project overview

### Community
- [GitHub Issues](https://github.com/2oby/ORAC-STT/issues)
- [GitHub Discussions](https://github.com/2oby/ORAC-STT/discussions)

---

**Last Updated:** October 17, 2025
**Version:** 0.2.0
**Author:** ORAC Team
