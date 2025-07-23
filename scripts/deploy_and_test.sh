#!/bin/bash
# Deploy and test ORAC STT service on Orin Nano

set -e

# Configuration
ORIN_HOST="orin3"
ORIN_USER="${ORIN_USER:-toby}"
PROJECT_NAME="orac-stt"
REMOTE_DIR="/home/${ORIN_USER}/${PROJECT_NAME}"

echo "=� Deploying ORAC STT to Orin Nano (${ORIN_HOST})"

# Clone or update repository
echo "📥 Updating code from Git..."
ssh ${ORIN_HOST} "
    if [ -d ${REMOTE_DIR}/.git ]; then
        echo 'Pulling latest changes...'
        cd ${REMOTE_DIR} && git pull origin master
    else
        echo 'Cloning repository...'
        rm -rf ${REMOTE_DIR}
        git clone https://github.com/2oby/ORAC-STT.git ${REMOTE_DIR}
    fi
"

# Build whisper.cpp if not already built
echo "🛠️ Building whisper.cpp on Jetson..."
ssh ${ORIN_HOST} "
    cd ${REMOTE_DIR}
    if [ ! -f third_party/whisper_cpp/bin/whisper-cli ]; then
        echo 'Building whisper.cpp for the first time...'
        chmod +x third_party/whisper_cpp/build_whisper_cpp.sh
        cd third_party/whisper_cpp && ./build_whisper_cpp.sh
    else
        echo 'whisper.cpp already built'
    fi
    
    # Copy shared libraries if not already done
    if [ ! -d third_party/whisper_cpp/lib ]; then
        echo 'Copying whisper.cpp shared libraries...'
        mkdir -p third_party/whisper_cpp/lib
        cp third_party/whisper_cpp/whisper.cpp/build/src/*.so* third_party/whisper_cpp/lib/ 2>/dev/null || true
        cp third_party/whisper_cpp/whisper.cpp/build/ggml/src/*.so* third_party/whisper_cpp/lib/ 2>/dev/null || true
        echo 'Shared libraries copied'
    else
        echo 'Shared libraries already available'
    fi
"

# Build Docker image on Orin
echo "=3 Building Docker image on Orin..."
ssh ${ORIN_HOST} "cd ${REMOTE_DIR} && docker build -t ${PROJECT_NAME}:latest ."

# Stop existing container if running
echo "=� Stopping existing container..."
ssh ${ORIN_HOST} "docker stop ${PROJECT_NAME} || true && docker rm ${PROJECT_NAME} || true"

# Run container
echo "�  Starting container..."
ssh ${ORIN_HOST} "docker run -d \
    --name ${PROJECT_NAME} \
    --gpus all \
    --restart unless-stopped \
    -p 8000:8000 \
    -v ${REMOTE_DIR}/models:/app/models \
    -v ${REMOTE_DIR}/logs:/app/logs \
    -v ${REMOTE_DIR}/certs:/app/certs \
    -v ${REMOTE_DIR}/third_party/whisper_cpp/bin:/app/third_party/whisper_cpp/bin:ro \
    -v ${REMOTE_DIR}/third_party/whisper_cpp/models:/app/models/whisper_cpp:ro \
    -v ${REMOTE_DIR}/third_party/whisper_cpp/lib:/usr/local/lib/whisper:ro \
    -e ORAC_COMMAND_API_URL=http://localhost:8001/command \
    -e USE_WHISPER_CPP=true \
    -e LD_LIBRARY_PATH=/usr/local/lib/whisper \
    ${PROJECT_NAME}:latest"

# Wait for service to start
echo "� Waiting for service to start..."
sleep 5

# Test health endpoint
echo "<� Testing health endpoint..."
if ssh ${ORIN_HOST} "curl -s http://localhost:8000/health" | grep -q "healthy"; then
    echo " Health check passed!"
else
    echo "L Health check failed!"
    ssh ${ORIN_HOST} "docker logs ${PROJECT_NAME}"
    exit 1
fi

# Test metrics endpoint
echo "=� Testing metrics endpoint..."
if ssh ${ORIN_HOST} "curl -s http://localhost:8000/metrics" | grep -q "orac_stt"; then
    echo " Metrics endpoint working!"
else
    echo "L Metrics endpoint failed!"
fi

# Show container logs
echo "=� Container logs:"
ssh ${ORIN_HOST} "docker logs --tail 20 ${PROJECT_NAME}"

echo "( Deployment complete!"
echo "< Service available at: http://${ORIN_HOST}:8000"