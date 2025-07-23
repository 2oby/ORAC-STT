#!/usr/bin/env python3
"""Test GPU availability and Whisper CUDA support."""

import torch
import whisper
import numpy as np

print("=== GPU Test for ORAC STT ===\n")

# Test PyTorch CUDA
print("1. PyTorch Configuration:")
print(f"   PyTorch version: {torch.__version__}")
print(f"   CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   CUDA version: {torch.version.cuda}")
    print(f"   GPU device: {torch.cuda.get_device_name(0)}")
    print(f"   GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
print()

# Test Whisper model loading
print("2. Whisper Model Test:")
try:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"   Loading whisper-tiny on {device}...")
    model = whisper.load_model("tiny", device=device)
    print(f"   Model loaded successfully on {device}")
    print(f"   Model device: {next(model.parameters()).device}")
    
    # Test inference
    print("\n3. Test Inference:")
    # Create a dummy audio (1 second of silence)
    audio = np.zeros(16000, dtype=np.float32)
    result = model.transcribe(audio, fp16=False)
    print(f"   Inference successful!")
    print(f"   Transcription result: '{result['text']}'")
    
except Exception as e:
    print(f"   Error: {e}")

print("\n=== Test Complete ===")