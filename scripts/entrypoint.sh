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

# Log helper
log() {
    echo "[entrypoint] $(date '+%Y-%m-%d %H:%M:%S') $1"
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
    $WHISPER_SERVER_BIN \
        --model "$WHISPER_MODEL" \
        --host "$WHISPER_SERVER_HOST" \
        --port "$WHISPER_SERVER_PORT" \
        --no-timestamps \
        --language en \
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

start_whisper_server

log "Starting ORAC STT main application..."
exec /usr/bin/python3.10 -m src.orac_stt.main "$@"
