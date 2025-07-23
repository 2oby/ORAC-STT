#!/bin/bash
set -e

echo "🔧 [1/7] Checking for 32GB swap file at /swapfile..."

if ! swapon --show | grep -q "/swapfile"; then
    echo "⚠️  No swapfile active — creating 32GB swap at /swapfile..."
    sudo swapoff -a || true
    sudo fallocate -l 32G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    grep -q "/swapfile" /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    sudo sysctl vm.swappiness=60
else
    echo "✅ Swapfile already exists and is active."
fi

echo "📊 Current swap status:"
swapon --show

echo "📦 [2/7] Installing minimal build dependencies..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    build-essential cmake git curl ca-certificates

echo "🔌 [3/7] Stopping graphical desktop to free memory..."
sudo systemctl stop gdm3 || sudo systemctl stop lightdm || sudo systemctl stop graphical.target
sudo systemctl start multi-user.target

echo "🧠 [4/7] Exporting memory-safe build flags..."
export MAKEFLAGS="-j1"
export GOMAXPROCS=1
export LDFLAGS="-Wl,--no-keep-memory -Wl,--reduce-memory-overheads"

echo "📥 [5/7] Cloning whisper.cpp..."
rm -rf whisper.cpp
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

echo "🛠️ [6/7] Building whisper.cpp with CUDA support for compute capability 8.7..."
# Build with CUDA support for Orin Nano
make clean
WHISPER_CUBLAS=1 CUDA_ARCH_LIST="87" make -j1

echo "📂 [7/7] Copying binaries and models to output folder..."
cd ..
mkdir -p bin models
rm -rf bin/*  # Clear old binaries
cp -v whisper.cpp/main bin/whisper || echo "Warning: main binary not found"
cp -v whisper.cpp/server bin/whisper-server || echo "Warning: server binary not found"
cp -v whisper.cpp/stream bin/whisper-stream || echo "Warning: stream binary not found"
cp -v whisper.cpp/bench bin/whisper-bench || echo "Warning: bench binary not found"

echo "📋 Listing copied binaries..."
ls -l bin/

echo "📥 Downloading base Whisper model..."
cd models
if [ ! -f "ggml-base.bin" ]; then
    echo "Downloading ggml-base model..."
    curl -L -o ggml-base.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
else
    echo "ggml-base.bin already exists"
fi

echo "✅ Build complete!"
echo "📍 Binaries are now in: ./bin/"
echo "🎤 Models are in: ./models/"
echo "🚀 Run with: ./bin/whisper -m ./models/ggml-base.bin audio.wav"