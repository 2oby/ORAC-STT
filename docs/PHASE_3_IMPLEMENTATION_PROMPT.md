# Phase 3 Implementation: Hey ORAC Heartbeat Integration

## Context
You are working on the ORAC STT system integration. Phase 2B (Topic Management) has been completed with the following capabilities:
- Topic registry with lazy registration from heartbeats
- Per-topic ORAC Core URL configuration
- Admin UI displaying topic cards with activity status
- Persistence of topic configurations in `/app/data/topics.yaml`

Reference the full integration flow in: `/docs/ORAC_INTEGRATION_FLOW.md`

## Current State
The ORAC STT service is running with:
- Heartbeat endpoint at `POST /heartbeat` accepting heartbeats with topic information
- Topic auto-registration when new topics arrive in heartbeats
- Admin UI at port 7272 showing registered topics with green/yellow/red status indicators
- Test topics currently hardcoded in heartbeat_manager.py (lines 88-91) that need removal

## Your Task: Implement Phase 3 - Hey ORAC Heartbeat Sender

### 1. Remove Test Topics from ORAC STT
- Location: `src/orac_stt/core/heartbeat_manager.py`
- Remove lines 88-91 that create test topics
- These were only for UI testing and should be replaced by real topics from Hey ORAC

### 2. Implement Hey ORAC Heartbeat Sender
Create a heartbeat sender in the Hey ORAC service that:

#### Heartbeat Message Structure
```python
{
    "instance_id": "hey-orac-{hostname}",
    "models": [
        {
            "name": "hey_orac",
            "topic": "{actual_wake_word}",  # e.g., "orac", "jarvis", "computer"
            "type": "wake_word",
            "status": "active",
            "metadata": {
                "wake_word": "{wake_word}",
                "trigger_phrase": "hey {wake_word}",
                "sensitivity": 0.5
            }
        }
    ],
    "timestamp": "2024-01-20T10:30:00Z",
    "metrics": {
        "activations_1h": 42,
        "last_activation": "2024-01-20T10:25:00Z"
    }
}
```

#### Implementation Requirements
- Send heartbeat every 30 seconds to ORAC STT at `http://orac-stt:7272/heartbeat`
- Include the actual wake word configured in Hey ORAC as the topic
- Track activation metrics (number of wake word detections)
- Handle connection failures gracefully with exponential backoff
- Start sending heartbeats immediately on service startup

### 3. Configuration Updates
- Add ORAC_STT_URL environment variable to Hey ORAC service
- Default to `http://localhost:7272` for local testing
- Production should use `http://orac-stt:7272` (Docker network name)

### 4. Testing Steps
1. Deploy updated ORAC STT without test topics
2. Deploy Hey ORAC with heartbeat sender
3. Verify topics appear in ORAC STT admin UI
4. Test wake word detection flow:
   - Say "Hey ORAC"
   - Verify heartbeat metrics update
   - Check topic card shows activity (green status)
   - Confirm audio is sent to ORAC STT for transcription

### 5. Validation Checklist
- [ ] Topics appear automatically in ORAC STT admin when Hey ORAC starts
- [ ] Topic status changes from red → yellow → green based on heartbeat timing
- [ ] Activation metrics update when wake word is detected
- [ ] Multiple Hey ORAC instances create separate topics if using different wake words
- [ ] Topic configuration (Core URL) persists across ORAC STT restarts

## Important Notes
- Topics are lazy-created: they only appear when the first heartbeat arrives
- Each unique wake word creates a separate topic
- The topic name should be lowercase (e.g., "orac", not "ORAC")
- Heartbeats serve dual purpose: health monitoring AND topic registration

## Files to Focus On
- Hey ORAC service code (implement heartbeat sender)
- `src/orac_stt/core/heartbeat_manager.py` (remove test topics)
- Docker Compose configuration (add environment variables)

## Expected Outcome
After implementation, the ORAC STT admin UI should show real topics from actual Hey ORAC instances, with live activity tracking based on wake word detections. The test topics should be gone, replaced by actual wake word topics like "orac", "jarvis", etc.