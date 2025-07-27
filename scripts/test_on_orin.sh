#!/bin/bash
# Test ORAC STT service directly on Orin Nano

set -e

ORIN_HOST="${1:-orin3}"

echo "🧪 Testing ORAC STT on ${ORIN_HOST}"

# Run tests via SSH
ssh ${ORIN_HOST} << 'EOF'
    # Check if container is running
    echo "🐳 Checking container status..."
    docker ps | grep orac-stt || echo "Container not running"
    
    # Test health endpoint
    echo "🏥 Testing health endpoint..."
    curl -s http://localhost:7272/health | jq . || echo "Health check failed"
    
    # Test metrics endpoint
    echo "📊 Testing metrics endpoint..."
    curl -s http://localhost:7272/metrics | head -20
    
    # Check GPU availability
    echo "🎮 Checking GPU..."
    nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv || echo "GPU check failed"
EOF