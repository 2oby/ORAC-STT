#!/bin/bash

# Fix ORAC STT Docker Container - Clean rebuild with proper Python dependencies
# This script rebuilds the container from scratch using --no-cache

set -e

echo "========================================="
echo "ORAC STT Container Fix Script"
echo "========================================="
echo

# Configuration
REMOTE_HOST="orin4"
REMOTE_USER="toby"
REMOTE_DIR="/home/toby/orac-stt"
LOCAL_DIR="/Users/2oby/pCloud Box/Projects/ORAC/ORAC STT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Syncing fixed files to Orin...${NC}"
echo "Copying Dockerfile.fixed and docker-compose.fixed.yml..."

# Copy the fixed files
scp "$LOCAL_DIR/Dockerfile.fixed" ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/
scp "$LOCAL_DIR/docker-compose.fixed.yml" ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/

# Also sync the source code and requirements
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.DS_Store' \
    "$LOCAL_DIR/src" "$LOCAL_DIR/requirements.txt" "$LOCAL_DIR/config.toml.example" \
    ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/

echo -e "${GREEN}Files synced successfully${NC}"
echo

echo -e "${YELLOW}Step 2: Stopping existing container...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "docker stop orac-stt 2>/dev/null || true"
ssh ${REMOTE_USER}@${REMOTE_HOST} "docker rm orac-stt 2>/dev/null || true"
echo -e "${GREEN}Existing container stopped${NC}"
echo

echo -e "${YELLOW}Step 3: Checking whisper.cpp binaries on host...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "ls -la ${REMOTE_DIR}/third_party/whisper_cpp/bin/ 2>/dev/null || echo 'bin directory not found'"
ssh ${REMOTE_USER}@${REMOTE_HOST} "ls -la ${REMOTE_DIR}/third_party/whisper_cpp/lib/ 2>/dev/null || echo 'lib directory not found'"
echo

echo -e "${YELLOW}Step 4: Building new image with --no-cache...${NC}"
echo "This will take a few minutes as we're rebuilding from scratch..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_DIR} && docker build --no-cache -f Dockerfile.fixed -t orac-stt:fixed ."

if [ $? -ne 0 ]; then
    echo -e "${RED}Docker build failed!${NC}"
    exit 1
fi
echo -e "${GREEN}Docker image built successfully${NC}"
echo

echo -e "${YELLOW}Step 5: Verifying Python dependencies in image...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "docker run --rm orac-stt:fixed python3.10 -c 'import uvicorn, fastapi, pydantic; print(\"Dependencies OK\")'"

if [ $? -ne 0 ]; then
    echo -e "${RED}Python dependencies verification failed!${NC}"
    exit 1
fi
echo -e "${GREEN}Python dependencies verified${NC}"
echo

echo -e "${YELLOW}Step 6: Starting container with docker-compose...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_DIR} && docker-compose -f docker-compose.fixed.yml up -d"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to start container!${NC}"
    exit 1
fi
echo -e "${GREEN}Container started${NC}"
echo

echo -e "${YELLOW}Step 7: Waiting for container to be ready...${NC}"
sleep 5

echo -e "${YELLOW}Step 8: Checking container status...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "docker ps | grep orac-stt"
echo

echo -e "${YELLOW}Step 9: Checking container logs...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "docker logs --tail 30 orac-stt"
echo

echo -e "${YELLOW}Step 10: Testing health endpoint...${NC}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "curl -s http://localhost:7272/health | python3 -m json.tool"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}ORAC STT container is now running!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    echo
    echo "Access points:"
    echo "  - Health: http://${REMOTE_HOST}:7272/health"
    echo "  - Metrics: http://${REMOTE_HOST}:7272/metrics"
    echo "  - API: http://${REMOTE_HOST}:7272/stt/v1/"
    echo
    echo "Monitor logs with:"
    echo "  ssh ${REMOTE_HOST} 'docker logs -f orac-stt'"
else
    echo -e "${RED}Health check failed - container may not be running correctly${NC}"
    echo "Check logs with: ssh ${REMOTE_HOST} 'docker logs orac-stt'"
    exit 1
fi