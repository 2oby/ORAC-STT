Requirements for ORAC STT Service (Orin Nano)

1. Ingress API

Endpoint /stt/v1/stream (HTTP POST WAV/PCM).

Headers: X-Model-Name, optional Authorization: Bearer …, Content-Type: audio/wav.

Max utterance 15 s; request timeout 20 s.

Respond 202 Accepted immediately, stream decoded text when done.

Stub gRPC bidirectional endpoint (disabled) with protobuf schema for v1.1.

2. Egress to Command API

POST JSON { "text": "...", "confidence": float, "lang": "en" } to Command API.

Map STT errors to 4xx/5xx codes; retry with exponential back‑off.

3. Audio & Model

Accept 16 kHz 16‑bit mono WAV.

Load selected model (Whisper‑tiny‑int8 default) via env/TOML.

Provide switch hook for future FLAC input.

4. Performance Targets

≤ 500 ms median from speech end to text delivered.

< 25 % CPU sustained on Orin Nano 8 GB.

5. Security & Pairing

Support mutual‑TLS with self‑signed certs.

First‑run pairing: 6‑digit PIN exchange via admin GUIs to trust peer fingerprint.

6. Robustness & Observability

Auto‑restart on GPU/driver failure.

Circuit breaker on repeated decode errors.

/metrics Prometheus and /health liveness endpoints.

7. Deployment

Containerised; mount model cache volume.

Provide systemd unit and compose example.

8. Future Hooks

Streaming partial ASR via gRPC.

Speaker ID and word‑level timestamps fields reserved in protobuf.