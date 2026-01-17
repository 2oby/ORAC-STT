#!/bin/bash
# ORAC STT entrypoint script
# Starts whisper-server in the background, then runs the main Python application

set -e

# Configuration
WHISPER_SERVER_BIN="/app/third_party/whisper_cpp/bin/whisper-server"
WHISPER_MODEL="/app/models/whisper_cpp/whisper/ggml-tiny.bin"
WHISPER_SERVER_PORT="${WHISPER_SERVER_PORT:-8080}"
WHISPER_SERVER_HOST="${WHISPER_SERVER_HOST:-127.0.0.1}"
USE_WHISPER_SERVER="${USE_WHISPER_SERVER:-false}"
CUDA_LIB_DIR="/usr/local/lib/whisper"
# Prompt to bias Whisper toward common words (fixes "lounge" being heard as "launch")
WHISPER_PROMPT="${WHISPER_PROMPT:-lounge cabinet lights kitchen bedroom bathroom office}"

# Log helper
log() {
    echo "[entrypoint] $(date '+%Y-%m-%d %H:%M:%S') $1"
}

# Decompress CUDA library if needed (stored compressed due to GitHub size limits)
decompress_cuda_lib() {
    local cuda_lib="$CUDA_LIB_DIR/libggml-cuda.so"
    local cuda_lib_gz="$CUDA_LIB_DIR/libggml-cuda.so.gz"

    if [ -f "$cuda_lib" ]; then
        log "CUDA library already decompressed"
        return 0
    fi

    if [ -f "$cuda_lib_gz" ]; then
        log "Decompressing CUDA library..."
        gunzip -k "$cuda_lib_gz"
        log "CUDA library decompressed"
        return 0
    fi

    log "WARNING: CUDA library not found (GPU acceleration unavailable)"
}

# Start whisper-server if enabled
start_whisper_server() {
    if [ "$USE_WHISPER_SERVER" != "true" ]; then
        log "whisper-server disabled (USE_WHISPER_SERVER=$USE_WHISPER_SERVER)"
        return 0
    fi

    if [ ! -f "$WHISPER_SERVER_BIN" ]; then
        log "ERROR: whisper-server binary not found at $WHISPER_SERVER_BIN"
        exit 1
    fi

    if [ ! -f "$WHISPER_MODEL" ]; then
        log "ERROR: Whisper model not found at $WHISPER_MODEL"
        exit 1
    fi

    log "Starting whisper-server on $WHISPER_SERVER_HOST:$WHISPER_SERVER_PORT..."

    # Start whisper-server in background
    # --prompt biases the model toward common location/device words
    log "Using whisper prompt: $WHISPER_PROMPT"
    # Use CPU-only mode to avoid GPU contention with llama-server
    # Whisper-tiny is small enough that CPU inference is still fast (~0.5-1s)
    $WHISPER_SERVER_BIN \
        --model "$WHISPER_MODEL" \
        --host "$WHISPER_SERVER_HOST" \
        --port "$WHISPER_SERVER_PORT" \
        --no-timestamps \
        --no-gpu \
        --language en \
        --prompt "$WHISPER_PROMPT" \
        2>&1 | while read line; do echo "[whisper-server] $line"; done &

    WHISPER_PID=$!
    log "whisper-server started with PID $WHISPER_PID"

    # Wait for server to be ready
    log "Waiting for whisper-server to be ready..."
    for i in $(seq 1 60); do
        if curl -s "http://$WHISPER_SERVER_HOST:$WHISPER_SERVER_PORT/" > /dev/null 2>&1; then
            log "whisper-server is ready!"
            return 0
        fi
        sleep 1
    done

    log "ERROR: whisper-server failed to start within 60 seconds"
    exit 1
}

# Cleanup on exit
cleanup() {
    log "Shutting down..."
    if [ -n "$WHISPER_PID" ]; then
        kill $WHISPER_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Main
log "ORAC STT entrypoint starting..."
log "USE_WHISPER_SERVER=$USE_WHISPER_SERVER"

# Decompress CUDA library if needed
decompress_cuda_lib

start_whisper_server

log "Starting ORAC STT main application..."
exec /usr/bin/python3.10 -m src.orac_stt.main "$@"
