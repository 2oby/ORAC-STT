#!/bin/bash
# Test whisper.cpp transcription functionality in ORAC STT
# This script should be run AFTER deploy_and_test.sh

set -e

echo "=== Testing Whisper.cpp Transcription in ORAC STT ==="
echo "Note: This script assumes ORAC STT is already deployed and running."
echo "      Run scripts/deploy_and_test.sh first if needed."
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ORIN_HOST="${ORIN_HOST:-orin4}"
ORIN_USER="${ORIN_USER:-toby}"
STT_URL="http://${ORIN_HOST}:7272"

echo "Configuration:"
echo "  STT Service URL: ${STT_URL}"
echo "  Orin Host: ${ORIN_HOST}"
echo

# Step 1: Check service health
echo -e "${YELLOW}Step 1: Checking service health...${NC}"
HEALTH_CHECK=$(curl -s "${STT_URL}/stt/v1/health" || echo "{}")
echo "Health check response:"
echo "${HEALTH_CHECK}" | jq . 2>/dev/null || echo "${HEALTH_CHECK}"

# Extract backend info
BACKEND=$(echo "${HEALTH_CHECK}" | jq -r '.backend' 2>/dev/null || echo "unknown")
MODEL=$(echo "${HEALTH_CHECK}" | jq -r '.model_name' 2>/dev/null || echo "unknown")
echo -e "Backend: ${BLUE}${BACKEND}${NC}"
echo -e "Model: ${BLUE}${MODEL}${NC}"
echo

# Step 2: Create test audio files
echo -e "${YELLOW}Step 2: Creating test audio files...${NC}"

# Test audio directory
TEST_DIR="/tmp/orac_stt_test_$$"
mkdir -p "${TEST_DIR}"

# Create a simple tone (likely to return empty)
TEST_TONE="${TEST_DIR}/test_tone.wav"
if command -v sox >/dev/null 2>&1; then
    sox -n -r 16000 -c 1 -b 16 "${TEST_TONE}" synth 2 sine 440
    echo "Created test tone: ${TEST_TONE}"
else
    ffmpeg -f lavfi -i "sine=frequency=440:duration=2" -ar 16000 -ac 1 -f wav "${TEST_TONE}" -y 2>/dev/null
    echo "Created test tone: ${TEST_TONE}"
fi

# Try to create speech audio
TEST_SPEECH="${TEST_DIR}/test_speech.wav"
if command -v espeak >/dev/null 2>&1; then
    espeak "Hello, testing ORAC speech to text service" -w "${TEST_SPEECH}" 2>/dev/null
    echo "Created speech audio with espeak: ${TEST_SPEECH}"
elif command -v say >/dev/null 2>&1; then
    # macOS text-to-speech
    say "Hello, testing ORAC speech to text service" -o "${TEST_SPEECH}" --data-format=LEI16@16000
    echo "Created speech audio with macOS say: ${TEST_SPEECH}"
else
    echo "No text-to-speech tool found. Using tone only."
    cp "${TEST_TONE}" "${TEST_SPEECH}"
fi

# Step 3: Test with tone (expected to be empty or minimal)
echo -e "${YELLOW}Step 3: Testing with tone audio...${NC}"
TONE_RESPONSE=$(curl -s -X POST "${STT_URL}/stt/v1/stream" \
    -F "file=@${TEST_TONE}" \
    -F "language=en" || echo "{}")

echo "Tone transcription response:"
echo "${TONE_RESPONSE}" | jq . 2>/dev/null || echo "${TONE_RESPONSE}"
echo

# Step 4: Test with speech audio
echo -e "${YELLOW}Step 4: Testing with speech audio...${NC}"
SPEECH_RESPONSE=$(curl -s -X POST "${STT_URL}/stt/v1/stream" \
    -F "file=@${TEST_SPEECH}" \
    -F "language=en" || echo "{}")

echo "Speech transcription response:"
echo "${SPEECH_RESPONSE}" | jq . 2>/dev/null || echo "${SPEECH_RESPONSE}"

# Check if we got text
TRANSCRIBED_TEXT=$(echo "${SPEECH_RESPONSE}" | jq -r '.text' 2>/dev/null || echo "")
if [ -n "${TRANSCRIBED_TEXT}" ] && [ "${TRANSCRIBED_TEXT}" != "null" ]; then
    echo -e "${GREEN}✓ Successfully transcribed: '${TRANSCRIBED_TEXT}'${NC}"
else
    echo -e "${RED}✗ No transcription returned${NC}"
fi
echo

# Step 5: Test with existing debug recordings
echo -e "${YELLOW}Step 5: Checking for existing debug recordings...${NC}"
DEBUG_RECORDINGS=$(curl -s "${STT_URL}/stt/v1/debug/recordings" || echo "{}")
RECORDING_COUNT=$(echo "${DEBUG_RECORDINGS}" | jq -r '.count' 2>/dev/null || echo "0")

if [ "${RECORDING_COUNT}" -gt "0" ]; then
    echo "Found ${RECORDING_COUNT} debug recordings"
    echo "${DEBUG_RECORDINGS}" | jq -r '.recordings[] | "\(.filename) - \(.duration_estimate)s"' 2>/dev/null || true
    
    # Test with the first debug recording
    FIRST_RECORDING=$(echo "${DEBUG_RECORDINGS}" | jq -r '.recordings[0].filename' 2>/dev/null || echo "")
    if [ -n "${FIRST_RECORDING}" ] && [ "${FIRST_RECORDING}" != "null" ]; then
        echo
        echo "Testing with debug recording: ${FIRST_RECORDING}"
        
        # Download and test the recording
        DEBUG_WAV="${TEST_DIR}/${FIRST_RECORDING}"
        curl -s "${STT_URL}/stt/v1/debug/recordings/${FIRST_RECORDING}" -o "${DEBUG_WAV}"
        
        DEBUG_RESPONSE=$(curl -s -X POST "${STT_URL}/stt/v1/stream" \
            -F "file=@${DEBUG_WAV}" \
            -F "language=en" || echo "{}")
        
        echo "Debug recording transcription:"
        echo "${DEBUG_RESPONSE}" | jq . 2>/dev/null || echo "${DEBUG_RESPONSE}"
    fi
else
    echo "No debug recordings found"
fi
echo

# Step 6: Test whisper.cpp directly on Orin
echo -e "${YELLOW}Step 6: Testing whisper.cpp CLI directly on Orin...${NC}"

# Copy test audio to Orin
scp -q "${TEST_SPEECH}" "${ORIN_USER}@${ORIN_HOST}:/tmp/test_speech.wav"

ssh "${ORIN_USER}@${ORIN_HOST}" << 'EOF'
    # Find whisper-cli binary
    WHISPER_BIN=$(find /home/toby/orac-stt -name "whisper-cli" -type f 2>/dev/null | head -1)
    MODEL_PATH=$(find /home/toby/orac-stt -name "ggml-tiny.bin" -type f 2>/dev/null | head -1)
    
    if [ -n "${WHISPER_BIN}" ] && [ -n "${MODEL_PATH}" ]; then
        echo "Found whisper-cli: ${WHISPER_BIN}"
        echo "Found model: ${MODEL_PATH}"
        
        # Test direct whisper.cpp execution
        echo "Running whisper.cpp directly..."
        ${WHISPER_BIN} -m ${MODEL_PATH} -f /tmp/test_speech.wav --no-timestamps 2>/dev/null || echo "Direct whisper.cpp test failed"
    else
        echo "Could not find whisper-cli or model on Orin"
    fi
    
    rm -f /tmp/test_speech.wav
EOF
echo

# Step 7: Check recent logs
echo -e "${YELLOW}Step 7: Recent ORAC STT logs...${NC}"
ssh "${ORIN_USER}@${ORIN_HOST}" "docker logs --tail 30 orac-stt | grep -E 'whisper|transcription|error|warning' || docker logs --tail 10 orac-stt"
echo

# Cleanup
rm -rf "${TEST_DIR}"

# Summary
echo -e "${BLUE}=== Test Summary ===${NC}"
echo
if [ -n "${TRANSCRIBED_TEXT}" ] && [ "${TRANSCRIBED_TEXT}" != "null" ]; then
    echo -e "${GREEN}✅ Whisper.cpp integration is working!${NC}"
    echo "   Transcribed: '${TRANSCRIBED_TEXT}'"
else
    echo -e "${RED}❌ Whisper.cpp integration may have issues${NC}"
    echo "   Check the logs above for error messages"
fi
echo
echo "Additional test options:"
echo "1. Test with your own audio file:"
echo "   curl -X POST ${STT_URL}/stt/v1/stream -F 'file=@your_audio.wav'"
echo
echo "2. Monitor logs in real-time:"
echo "   ssh ${ORIN_HOST} 'docker logs -f orac-stt'"
echo
echo "3. Check all debug recordings:"
echo "   curl ${STT_URL}/stt/v1/debug/recordings | jq ."