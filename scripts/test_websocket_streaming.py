#!/usr/bin/env python3
"""Test script for WebSocket streaming transcription endpoint.

Usage:
    # Test with generated audio (sine wave)
    python scripts/test_websocket_streaming.py

    # Test with a WAV file
    python scripts/test_websocket_streaming.py --file test.wav

    # Test against deployed server
    python scripts/test_websocket_streaming.py --url ws://192.168.8.192:7272/stt/v1/ws/stream/test
"""

import argparse
import asyncio
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)


def generate_test_audio(duration_ms: int = 2000, sample_rate: int = 16000) -> bytes:
    """Generate test audio (440Hz sine wave) as int16 bytes.

    Args:
        duration_ms: Duration in milliseconds
        sample_rate: Sample rate in Hz

    Returns:
        Raw int16 audio bytes
    """
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, dtype=np.float32)

    # Generate 440Hz sine wave at 50% amplitude
    audio = (np.sin(2 * np.pi * 440 * t) * 0.5 * 32767).astype(np.int16)

    return audio.tobytes()


def load_wav_file(filepath: Path) -> tuple[bytes, int]:
    """Load WAV file and return as int16 bytes.

    Args:
        filepath: Path to WAV file

    Returns:
        Tuple of (audio bytes as int16, sample rate)
    """
    import wave

    with wave.open(str(filepath), 'rb') as wav:
        sample_rate = wav.getframerate()
        n_channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frames = wav.readframes(wav.getnframes())

    # Convert to mono int16 if needed
    if sample_width == 2:
        audio = np.frombuffer(frames, dtype=np.int16)
    elif sample_width == 4:
        audio = (np.frombuffer(frames, dtype=np.int32) / 65536).astype(np.int16)
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    # Convert stereo to mono
    if n_channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1).astype(np.int16)

    return audio.tobytes(), sample_rate


async def test_websocket_streaming(
    url: str,
    audio_bytes: bytes,
    chunk_size: int = 2560,  # 80ms at 16kHz (1280 samples * 2 bytes)
    chunk_delay_ms: int = 80
):
    """Test WebSocket streaming endpoint.

    Args:
        url: WebSocket URL
        audio_bytes: Audio data as int16 bytes
        chunk_size: Size of each chunk in bytes
        chunk_delay_ms: Delay between chunks in ms (simulate real-time)
    """
    print(f"Connecting to {url}...")

    try:
        async with websockets.connect(url) as ws:
            print("Connected!")

            # Send config with timing info
            config = {
                "type": "config",
                "wake_word_time": time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
            await ws.send(json.dumps(config))
            print(f"Sent config: {config}")

            # Stream audio in chunks
            total_bytes = len(audio_bytes)
            sent_bytes = 0
            chunk_count = 0
            start_time = time.time()

            print(f"Streaming {total_bytes} bytes of audio...")

            while sent_bytes < total_bytes:
                chunk = audio_bytes[sent_bytes:sent_bytes + chunk_size]
                await ws.send(chunk)
                sent_bytes += len(chunk)
                chunk_count += 1

                # Simulate real-time streaming
                if chunk_delay_ms > 0:
                    await asyncio.sleep(chunk_delay_ms / 1000)

                # Progress indicator
                if chunk_count % 10 == 0:
                    print(f"  Sent {sent_bytes}/{total_bytes} bytes ({chunk_count} chunks)")

            stream_time = time.time() - start_time
            print(f"Finished streaming in {stream_time:.2f}s ({chunk_count} chunks)")

            # Send end signal
            end_signal = {"type": "end"}
            await ws.send(json.dumps(end_signal))
            print("Sent end signal, waiting for transcription...")

            # Wait for response
            response = await ws.recv()
            total_time = time.time() - start_time

            # Parse and display result
            result = json.loads(response)
            print("\n" + "=" * 50)
            print("TRANSCRIPTION RESULT")
            print("=" * 50)
            print(f"Text: {result.get('text', '(empty)')}")
            print(f"Confidence: {result.get('confidence', 0):.2f}")
            print(f"Language: {result.get('language', 'unknown')}")
            print(f"Audio duration: {result.get('duration', 0):.2f}s")
            print(f"Processing time: {result.get('processing_time', 0):.3f}s")
            print(f"Total round-trip: {total_time:.2f}s")
            print("=" * 50)

            return result

    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {e}")
        return None
    except ConnectionRefusedError:
        print(f"Connection refused. Is the server running at {url}?")
        return None


def main():
    parser = argparse.ArgumentParser(description="Test WebSocket streaming transcription")
    parser.add_argument(
        "--url",
        default="ws://localhost:7272/stt/v1/ws/stream/test",
        help="WebSocket URL"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="WAV file to stream (optional, uses generated audio if not provided)"
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=80,
        help="Chunk size in milliseconds"
    )
    parser.add_argument(
        "--no-delay",
        action="store_true",
        help="Send chunks as fast as possible (no real-time simulation)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=2000,
        help="Duration of generated test audio in ms"
    )

    args = parser.parse_args()

    # Load or generate audio
    if args.file:
        if not args.file.exists():
            print(f"File not found: {args.file}")
            sys.exit(1)
        print(f"Loading audio from {args.file}...")
        audio_bytes, sample_rate = load_wav_file(args.file)
        if sample_rate != 16000:
            print(f"Warning: Sample rate is {sample_rate}Hz, expected 16000Hz")
    else:
        print(f"Generating {args.duration}ms of test audio...")
        audio_bytes = generate_test_audio(args.duration)

    # Calculate chunk size in bytes (int16 = 2 bytes per sample)
    chunk_size = int(16000 * args.chunk_ms / 1000) * 2

    print(f"Audio size: {len(audio_bytes)} bytes")
    print(f"Chunk size: {chunk_size} bytes ({args.chunk_ms}ms)")
    print()

    # Run test
    asyncio.run(test_websocket_streaming(
        url=args.url,
        audio_bytes=audio_bytes,
        chunk_size=chunk_size,
        chunk_delay_ms=0 if args.no_delay else args.chunk_ms
    ))


if __name__ == "__main__":
    main()
