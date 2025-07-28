#!/usr/bin/env python3
"""Test script to verify whisper.cpp fixes in ORAC STT."""

import sys
import os
import wave
import numpy as np
import tempfile
from pathlib import Path

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from orac_stt.models.whisper_cpp import WhisperCppModel
from orac_stt.utils.logging import get_logger

logger = get_logger(__name__)


def create_test_audio(duration=3.0, frequency=440.0, sample_rate=16000):
    """Create a test audio signal (sine wave)."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # Create a sine wave
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    # Add some silence at beginning and end
    silence = np.zeros(int(0.5 * sample_rate))
    audio = np.concatenate([silence, audio, silence])
    
    return audio.astype(np.float32)


def test_whisper_cpp_direct():
    """Test the WhisperCppModel directly."""
    print("\n=== Testing WhisperCppModel directly ===")
    
    # Check if model exists
    model_path = "/app/models/ggml-tiny.bin"
    whisper_bin = "/app/third_party/whisper_cpp/bin/whisper-cli"
    
    # For local testing, use alternative paths
    if not Path(model_path).exists():
        model_path = str(Path.home() / ".cache/whisper/ggml-tiny.bin")
        whisper_bin = "whisper-cli"  # Assume it's in PATH
    
    print(f"Model path: {model_path}")
    print(f"Whisper binary: {whisper_bin}")
    
    try:
        # Initialize model
        model = WhisperCppModel(
            model_path=model_path,
            whisper_bin=whisper_bin,
            device="cpu"  # Use CPU for testing
        )
        
        # Create test audio
        print("\nCreating test audio...")
        audio = create_test_audio(duration=2.0)
        print(f"Audio shape: {audio.shape}, dtype: {audio.dtype}")
        print(f"Audio range: [{audio.min():.3f}, {audio.max():.3f}]")
        
        # Test transcription
        print("\nTesting transcription...")
        result = model.transcribe(audio, sample_rate=16000)
        
        print(f"\nResult: {result}")
        print(f"Text: '{result.get('text', '')}'")
        print(f"Confidence: {result.get('confidence', 0.0)}")
        
        # Test with a real audio file if available
        test_wav_path = Path("test.wav")
        if test_wav_path.exists():
            print(f"\n\nTesting with real audio file: {test_wav_path}")
            
            # Load the WAV file
            with wave.open(str(test_wav_path), 'rb') as wav:
                frames = wav.readframes(wav.getnframes())
                audio_data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                sample_rate = wav.getframerate()
            
            print(f"Loaded audio: {len(audio_data)/sample_rate:.2f}s at {sample_rate}Hz")
            
            # Transcribe
            result = model.transcribe(audio_data, sample_rate=sample_rate)
            print(f"\nTranscription: '{result.get('text', '')}'")
            print(f"Confidence: {result.get('confidence', 0.0)}")
        
        print("\n✅ WhisperCppModel test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error testing WhisperCppModel: {e}")
        import traceback
        traceback.print_exc()


def test_unified_loader():
    """Test the UnifiedWhisperLoader."""
    print("\n\n=== Testing UnifiedWhisperLoader ===")
    
    from orac_stt.models.unified_loader import UnifiedWhisperLoader
    from orac_stt.config.settings import ModelConfig
    
    try:
        # Create model config
        config = ModelConfig(
            name="whisper-tiny",
            device="cpu",
            cache_dir=Path.home() / ".cache/whisper"
        )
        
        # Force whisper.cpp backend
        os.environ["USE_WHISPER_CPP"] = "true"
        
        # Initialize loader
        loader = UnifiedWhisperLoader(config)
        print(f"Backend: {'whisper.cpp' if loader.use_whisper_cpp else 'PyTorch'}")
        
        # Create test audio
        audio = create_test_audio(duration=2.0)
        
        # Test transcription
        print("\nTesting transcription...")
        result = loader.transcribe(audio, sample_rate=16000)
        
        print(f"\nResult: {result}")
        print(f"Text: '{result.get('text', '')}'")
        
        print("\n✅ UnifiedWhisperLoader test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error testing UnifiedWhisperLoader: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Test both components
    test_whisper_cpp_direct()
    test_unified_loader()
    
    print("\n\n=== Test Summary ===")
    print("If you see transcribed text above (even if it's empty for the sine wave),")
    print("then the whisper.cpp integration is working correctly!")
    print("\nTo test with real audio, place a 'test.wav' file in this directory.")