# ORAC STT Test Suite

This directory contains the test suite for ORAC STT.

## Structure

```
tests/
├── conftest.py              # Shared pytest fixtures
├── unit/                    # Unit tests (isolated component tests)
│   ├── test_command_buffer.py
│   ├── test_audio_validator.py (TODO)
│   ├── test_config_loader.py (TODO)
│   └── ...
├── integration/             # Integration tests (multiple components)
│   ├── test_health_endpoint.py
│   ├── test_stt_endpoint.py (TODO)
│   └── ...
├── fixtures/                # Test data and fixtures
│   ├── audio_samples/       # Test audio files
│   └── config/              # Test configuration files
└── manual/                  # Manual test scripts (not automated)
    └── test_whisper_fix.py
```

## Running Tests

### Run all tests
```bash
pytest tests/ -v
```

### Run with coverage
```bash
pytest tests/ -v --cov=src/orac_stt --cov-report=term-missing
```

### Run only unit tests
```bash
pytest tests/unit/ -v
```

### Run only integration tests
```bash
pytest tests/integration/ -v
```

### Run specific test file
```bash
pytest tests/unit/test_command_buffer.py -v
```

## Writing Tests

### Unit Tests
Unit tests should:
- Test a single component in isolation
- Use mocks for dependencies
- Be fast (< 100ms per test)
- Not require external services

Example:
```python
def test_command_buffer_initialization():
    buffer = CommandBuffer(max_size=3)
    assert buffer.max_size == 3
```

### Integration Tests
Integration tests should:
- Test multiple components working together
- Use real dependencies when possible
- Test API endpoints end-to-end
- Verify the system works as a whole

Example:
```python
def test_health_endpoint(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
```

## Test Coverage Goals

- **Phase 1**: 20% coverage (foundation)
- **Phase 2**: 40% coverage (core functionality)
- **Phase 3**: 60%+ coverage (production ready)

## Current Status

**Phase 1 Complete:**
- Test structure established
- Basic unit tests for CommandBuffer
- Basic integration tests for health endpoint
- Shared fixtures in conftest.py

**TODO:**
- Add unit tests for audio processing
- Add unit tests for configuration
- Add integration tests for STT endpoint
- Add test audio fixtures
- Expand test coverage to 40%
