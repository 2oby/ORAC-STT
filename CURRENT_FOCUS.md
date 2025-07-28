# ORAC STT Service - Project Plan

## 🎯 NEXT PHASE: Admin Web Interface (2025-07-28)

### Requirements for Admin Web Interface

**Core Features:**
1. **Model Selection**
   - Dropdown/selector to switch between available whisper models (tiny/base/small/medium)
   - Real-time model switching without service restart
   - Display current model info (size, performance characteristics)

2. **Recent Commands Dashboard**
   - Display last 5 transcribed commands as tiles
   - Each tile shows:
     - Transcribed text
     - Timestamp
     - Duration
     - Confidence score
     - Play button for audio playback
   - New commands flash red when they arrive (like Hey_Orac activation)
   - Real-time updates via WebSocket

3. **Visual Design**
   - Cyberpunk aesthetic matching Hey_Orac
   - Green on black color scheme
   - Pixel art styling
   - Retro terminal font (e.g., "Courier New" or similar)
   - Glowing/neon effects for active elements
   - Red flash animation for new commands

**Technical Implementation:**
- **Frontend**: Single-page application with real-time updates
- **Backend**: FastAPI endpoints for model management and command history
- **WebSocket**: Real-time streaming of new transcriptions
- **Audio Storage**: Keep last 5 audio files for playback
- **State Management**: Track current model and command history

### Implementation Plan

**Phase 1: Backend Infrastructure (Priority: HIGH)**
1. **Create Command History Module** (`src/orac_stt/history/`):
   - In-memory circular buffer for last 5 commands
   - Store: transcription, audio file path, timestamp, duration, confidence
   - Thread-safe access for concurrent reads/writes
   
2. **Extend Audio Storage**:
   - Modify `save_debug_recording()` to save last 5 audio files
   - Create dedicated directory for command history audio
   - Implement cleanup of old files

3. **Add Model Management API**:
   - GET `/admin/models` - List available models with current selection
   - POST `/admin/models/select` - Switch active model
   - Add model info (size, performance stats)

4. **Create Admin API Router** (`src/orac_stt/api/admin.py`):
   - GET `/admin/commands` - Get last 5 commands
   - GET `/admin/commands/{id}/audio` - Stream audio file
   - WebSocket `/admin/ws` - Real-time command updates

**Phase 2: Frontend Development (Priority: HIGH)**
1. **Create Static Web Assets** (`src/orac_stt/web/`):
   - `static/` - CSS, JS, fonts, images
   - `templates/` - HTML templates
   - Use vanilla JS or lightweight framework for simplicity

2. **Design Cyberpunk UI**:
   - Base CSS on Hey_Orac's style.css
   - Green (#00ff00) on black (#000000) theme
   - Pixel art borders and effects
   - Monospace font (Courier New or custom pixel font)

3. **Implement Dashboard Layout**:
   - Header with ORAC STT branding
   - Model selector dropdown (top right)
   - Command tiles grid (main area)
   - Status indicators (connected, current model)

4. **Command Tile Component**:
   - Black background with green border
   - Flash red animation on new command
   - Display: text, timestamp, duration, confidence
   - Audio player controls (play/pause)

**Phase 3: Real-time Integration (Priority: MEDIUM)**
1. **WebSocket Implementation**:
   - Connect on page load
   - Receive new command notifications
   - Update UI with new tiles
   - Handle reconnection logic

2. **Audio Playback**:
   - HTML5 audio element per tile
   - Stream audio from backend
   - Visual feedback during playback

3. **Model Switching**:
   - Dropdown triggers API call
   - Show loading state during switch
   - Update UI with new model info
   - Persist selection

**Phase 4: Polish & Testing (Priority: LOW)**
1. **Animations & Effects**:
   - Smooth transitions for new tiles
   - Glowing effects on hover
   - Loading animations
   - Error state handling

2. **Responsive Design**:
   - Mobile-friendly layout
   - Touch controls for audio
   - Adaptive grid layout

3. **Error Handling**:
   - Connection loss indicators
   - Retry mechanisms
   - User-friendly error messages

### File Structure
```
src/orac_stt/
├── api/
│   ├── admin.py          # New admin endpoints
│   └── stt.py            # Modified to save command history
├── history/
│   ├── __init__.py
│   └── command_buffer.py  # Command history management
├── web/
│   ├── static/
│   │   ├── css/
│   │   │   └── admin.css  # Cyberpunk styling
│   │   ├── js/
│   │   │   └── admin.js   # Dashboard logic
│   │   └── fonts/         # Pixel/retro fonts
│   └── templates/
│       └── admin.html     # Dashboard template
└── main.py               # Mount admin routes
```

### Implementation Decisions:
1. **Authentication**: No authentication required (matching current approach)
2. **Persistence**: In-memory storage is sufficient for command history
3. **Audio Format**: Keep as WAV (no conversion needed)
4. **Model Switching**: Brief interruption (2-3 seconds) is acceptable
5. **Browser Support**: Modern browsers only (following Hey_Orac's approach)
6. **Architecture**: Follow Hey_Orac's patterns and design (don't reinvent the wheel)
7. **Communication**: Use same interprocess communication patterns as Hey_Orac
8. **Port**: Serve admin interface on same port as API (7272) for simplicity

---

## Current Status (2025-07-23 - whisper.cpp Complete)

### 🚀 MAJOR UPDATE: Switched to whisper.cpp for GPU Support!

**Why whisper.cpp?**
- ORAC project uses llama.cpp (C++ implementation) with native CUDA support
- PyTorch wheels for Jetson have CUDA compatibility issues
- whisper.cpp provides better performance and smaller footprint on edge devices

**Implementation Changes:**
- ✅ **Created whisper.cpp build script** - Compiles with CUDA support for compute capability 8.7
- ✅ **Updated Dockerfile** - Removed PyTorch, now mounts whisper.cpp binaries
- ✅ **Python wrapper created** - `WhisperCppModel` class wraps binary execution
- ✅ **Unified loader implemented** - Supports both whisper.cpp and PyTorch backends
- ✅ **Deployment script updated** - Builds whisper.cpp on device, mounts binaries

**Container Architecture:**
```
nvidia/cuda:12.6.0-runtime (base)
├── FastAPI application
├── whisper.cpp binaries (mounted)
└── GGML models (mounted)
```

**Benefits:**
- Container size: ~500MB (vs 3-4GB with PyTorch)
- Native CUDA optimization for Jetson/Orin
- Consistent with ORAC's C++ approach
- Better performance and memory efficiency

### 🎉 Phase 1: Core Architecture & Setup - ✅ **COMPLETE**
- Python package structure with organized modules
- Configuration management supporting TOML files and environment variables
- Logging framework with JSON and standard formats
- Main application entry point with FastAPI
- Health check endpoints (/health, /health/live, /health/ready)
- Prometheus metrics endpoint with comprehensive metrics collection
- Deployment scripts for Orin Nano (SSH to orin3)

### 🔄 Phase 2: Audio Processing Pipeline - **80% Complete**
**Completed:**
- ✅ WAV file validation (16kHz, 16-bit mono)
- ✅ Audio duration validation (max 15s)
- ✅ Audio buffer management for streaming
- ✅ FLAC support hook (stubbed for future)
- ✅ Whisper model loader with caching
- ✅ GPU/CPU fallback handling
- ✅ **NEW: Full ML dependencies installed**
- ✅ **NEW: GPU acceleration enabled**

**Remaining:**
- ⏳ Model inference wrapper implementation
- ⏳ Audio-to-text pipeline connection
- ⏳ Confidence score extraction
- ⏳ Language detection

### ✅ **DEPLOYMENT & TESTING SUCCESS - whisper.cpp Fully Working!**

**2025-07-23 Final Update:**
- ✅ **Container deployed successfully** with GPU support (CUDA 12.6) 
- ✅ **whisper.cpp built and compiled** with CUDA for compute capability 8.7
- ✅ **All models downloaded**: tiny (75MB), base (142MB), small (466MB), medium (1.5GB)
- ✅ **Binaries mounted correctly** in container at `/app/third_party/whisper_cpp/bin/`
- ✅ **GPU acceleration confirmed** via nvidia-smi in container
- ✅ **whisper-cli tested and working** - All binaries functional with GPU support
- ✅ **Health endpoint responding** - Container ready for STT endpoint implementation
- ✅ **Documentation updated** - README.md and CURRENT_FOCUS.md reflect whisper.cpp integration
- ✅ **Deploy script fixed** - Now checks for `whisper-cli` instead of `whisper`

**Available Models:**
```bash
/home/toby/orac-stt/third_party/whisper_cpp/models/whisper/
├── ggml-tiny.bin   (75MB)   - Fastest inference, basic accuracy
├── ggml-base.bin   (142MB)  - Good balance of speed/accuracy (recommended)
├── ggml-small.bin  (466MB)  - Better accuracy, slower
└── ggml-medium.bin (1.5GB)  - Best accuracy, much slower
```

**Available Binaries:**
```bash
/home/toby/orac-stt/third_party/whisper_cpp/bin/
├── whisper-cli     - Main transcription binary
├── whisper-server  - HTTP server mode
├── quantize        - Model quantization tool
└── whisper-bench   - Performance benchmarking
```

### 🎯 CURRENT STATUS: STT API Working, Final Debugging (2025-07-26)

**🎉 MAJOR PROGRESS: Core Transcription Pipeline Confirmed Working!**
- ✅ FastAPI endpoint `/stt/v1/stream` operational on port 7272
- ✅ Whisper.cpp binary working with GPU acceleration 
- ✅ Direct test: "Testing testing ABC Mary had a little tree" transcribed correctly
- ✅ Model loading, audio processing, and transcription pipeline functional

**🔧 CURRENT DEBUGGING: API Integration Issues**
1. **Model Path Fixed**: Updated cache_dir to `/app/models/whisper_cpp/whisper/` (correct location)
2. **GPU Flag Fixed**: Removed invalid `--gpu` flag (whisper.cpp uses `--no-gpu` to disable)
3. **File Access Issue**: API temporary files not accessible to whisper-cli in container
   - Direct whisper-cli test works: transcribes correctly with GPU
   - API endpoint returns empty results: file access/path issue

**Next Steps**: Fix temporary file access between FastAPI and whisper-cli subprocess

1. **Complete STT Endpoint Implementation**
   - **URGENT**: Fix python-multipart dependency in Dockerfile
   - Connect audio processor to unified loader (whisper.cpp backend)
   - Implement streaming response pattern for `/stt/v1/stream`
   - Add proper error handling and model loading
   - Test end-to-end: audio upload → whisper.cpp → transcription response

2. **Performance Testing & Optimization**
   - Benchmark inference times with different models (tiny/base/small)
   - Monitor GPU utilization during transcription
   - Optimize for <500ms latency target

## Technical Architecture Update

### ✅ whisper.cpp Architecture
```
┌─────────────────────────────────────────────┐
│          NVIDIA CUDA 12.6 Runtime           │
│                                             │
│  ┌─────────────┐    ┌──────────────────┐  │
│  │ whisper.cpp │    │   GGML Models   │  │
│  │  with CUDA  │───▶│  (Quantized)    │  │
│  │   cuBLAS    │    │   Efficient     │  │
│  └─────────────┘    └──────────────────┘  │
│         ↑                                   │
│         │ (subprocess)                      │
│  ┌─────────────────────────────────────┐  │
│  │        FastAPI Application          │  │
│  │  - WhisperCppModel wrapper          │  │
│  │  - Audio validation & processing    │  │
│  │  - Streaming responses              │  │
│  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 🔄 Container Size & Build Time
- **PyTorch approach**: ~3-4GB container (abandoned due to CUDA issues)
- **whisper.cpp approach**: ~500MB container + mounted binaries
- **Build time**: Container ~1 min, whisper.cpp ~10-15 min (one-time)
- **GPU memory**: Shared with system RAM on Orin
- **Model sizes**: GGML models are 4-8x smaller than PyTorch equivalents

## Deployment Commands Reference

```bash
# Deploy with GPU support
cd scripts && ./deploy_and_test.sh

# Test GPU availability
ssh orin3 "docker exec orac-stt nvidia-smi"
ssh orin3 "docker exec orac-stt python -c 'import torch; print(torch.cuda.is_available())'"

# Run GPU test script
ssh orin3 "docker exec orac-stt python scripts/test_gpu.py"

# Monitor GPU usage
ssh orin3 "nvidia-smi dmon -s pucvmet -i 0"

# Check container logs
ssh orin3 "docker logs -f orac-stt"
```

## Performance Expectations

### With GPU Acceleration
- **Model loading**: ~2-3 seconds (first time), <1s (cached)
- **Inference latency**: 50-200ms for 15s audio (GPU)
- **CPU usage**: <10% during inference (GPU offload)
- **GPU usage**: 20-40% during active transcription
- **Memory**: ~1-2GB for Whisper-tiny model

### Comparison to CPU-only
- **CPU inference**: 500-2000ms for 15s audio
- **CPU usage**: 80-100% during inference
- **Battery/thermal**: Significant improvement with GPU

## Next Session Goals

1. **Validate GPU functionality** - Run test script
2. **Implement inference wrapper** - Complete Phase 2
3. **Create STT endpoint** - Start Phase 3
4. **Performance benchmarking** - Measure GPU vs CPU
5. **End-to-end testing** - Audio file → transcription

---

## Full Project Status Overview

### Phase 1: Core Architecture & Setup - ✅ **100% COMPLETE**

### Phase 2: Audio Processing Pipeline - 🔄 **80% Complete**
- ✅ All audio validation and processing modules
- ✅ Model loader architecture
- ✅ GPU support infrastructure
- ⏳ Inference wrapper and pipeline integration

### Phase 3: API Implementation - 🔄 **0% Complete**
- ⏳ STT endpoint, streaming responses, Command API integration

### Phase 4: Security & Authentication - ⏳ **0% Complete**

### Phase 5: Performance & Robustness - 🔄 **10% Complete**
- ✅ GPU optimization enabled
- ⏳ Further optimization needed

### Phase 6: Containerization & Deployment - 🔄 **60% Complete**
- ✅ GPU-enabled Dockerfile
- ✅ Deployment scripts with GPU support
- ⏳ Resource limits and optimization

### Phase 7: Testing & Validation - ⏳ **5% Complete**
- ✅ GPU test script created
- ⏳ Comprehensive test suite needed

### Phase 8: Documentation & Finalization - 🔄 **25% Complete**

**Overall Project Progress: 45% Complete** (+10% with GPU enablement)