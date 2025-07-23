# ORAC STT Service

The ORAC STT (Speech-to-Text) Service is designed to run on NVIDIA Orin Nano, providing fast, robust, and secure speech-to-text conversion for the ORAC system. It receives audio streams from the Hey ORAC wake word service and transcribes them using optimized Whisper models.

## Key Features

- **HTTP API**: Accepts POST requests at `/stt/v1/stream` for 16kHz 16-bit mono WAV/PCM audio. Supports model selection via `X-Model-Name` header and optional Bearer token authentication.
- **gRPC Stub**: Includes a bidirectional gRPC endpoint (disabled by default) with protobuf schema for future streaming support.
- **Model Management**: Loads quantized Whisper models (default: whisper-tiny-int8) with configuration via environment variables or TOML. Designed for easy model switching and future FLAC support.
- **Egress to Command API**: Posts transcribed text, confidence, and language to the Command API, with robust error handling and exponential backoff retries.
- **Performance**: Targets <500ms median latency from speech end to text, and <25% sustained CPU usage on Orin Nano 8GB.
- **Security**: Implements mutual TLS (mTLS) with self-signed certificates and a 6-digit PIN pairing process for secure first-run setup.
- **Observability**: Provides Prometheus `/metrics` and `/health` endpoints for monitoring, and includes circuit breaker logic for repeated decode errors.
- **Deployment**: Fully containerized, with support for model cache volume mounts, systemd unit, and Docker Compose deployment.

## Technical Highlights

- **Audio Format**: 16kHz, 16-bit mono WAV (FLAC support planned)
- **API Response**: Responds 202 Accepted immediately, streams decoded text when ready
- **Robustness**: Auto-restarts on GPU/driver failure
- **Future Hooks**: Reserved fields for speaker ID and word-level timestamps in protobuf; planned streaming partial ASR via gRPC

## Configuration

The service uses a configuration file system with environment variable overrides:

1. **Copy the template**: `cp config.toml.example config.toml`
2. **Edit your settings**: Modify `config.toml` for your environment
3. **Override with env vars**: Use `ORAC_` prefix (e.g., `ORAC_LOG_LEVEL=DEBUG`)

### Configuration Sections:
- **App settings**: Logging, environment mode
- **Model**: Whisper model selection, GPU/CPU device, cache directory
- **API**: Host, port, timeouts, audio duration limits
- **Command API**: Downstream service integration
- **Security**: TLS/mTLS certificates and settings

## Getting Started

### Quick Deploy to Orin Nano
```bash
# Deploy and test
cd scripts
./deploy_and_test.sh

# Check logs
ssh orin3 "docker logs -f orac-stt"

# Test endpoints
curl http://orin3:8000/health
curl http://orin3:8000/metrics
```

### Development
1. Copy and customize configuration: `cp config.toml.example config.toml`
2. Build and deploy the service using Docker Compose or systemd
3. Send audio to `/stt/v1/stream` and receive transcriptions
4. Monitor health and metrics endpoints for observability

For detailed setup, deployment, and API usage, see the `CURRENT_FOCUS.md` file.
