# LiveKit Voice Worker

This service runs a dedicated LiveKit worker for realtime interview voice sessions.

## Security and Guardrails

- Room allowlist by prefix (`WORKER_ROOM_PREFIX`)
- Optional participant identity allowlist (`WORKER_ALLOWED_IDENTITY_PREFIXES`)
- Prompt-injection, off-topic, and profanity filtering
- Burst turn rate limiting (`WORKER_RATE_LIMIT_WINDOW_SECONDS`, `WORKER_RATE_LIMIT_MAX_TURNS`)
- Repeated refusal threshold lockout (`WORKER_MAX_REFUSALS_PER_SESSION`)
- Max turns per session (`WORKER_MAX_TURNS_PER_SESSION`)
- Max user/assistant message size limits
- Min interval between turns for abuse/race protection
- Structured abuse telemetry events (`WORKER_TELEMETRY_ENABLED`)
- Optional health/security alert webhook (`WORKER_ALERT_WEBHOOK_URL`)
- Fail-closed startup validation for missing critical secrets
- Fail-open TTS mode when ElevenLabs credits are exhausted (`WORKER_TTS_FAIL_OPEN`)

## Dispatch Resilience

The backend can auto-dispatch this worker into candidate rooms with bounded retries and exponential backoff:
- `LIVEKIT_DISPATCH_MAX_RETRIES`
- `LIVEKIT_DISPATCH_INITIAL_BACKOFF_SECONDS`
- `LIVEKIT_DISPATCH_MAX_BACKOFF_SECONDS`
- `LIVEKIT_DISPATCH_BACKOFF_MULTIPLIER`

## Required Environment Variables

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `GROQ_API_KEY`
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `WORKER_BACKEND_API_BASE_URL` (default: `http://backend:8000/api`)
- `WORKER_INTERNAL_API_KEY` (must match backend `WORKER_INTERNAL_API_KEY`)

STT provider options:
- `WORKER_STT_PROVIDER=openai` (default, uses Groq OpenAI-compatible STT)
- `WORKER_STT_PROVIDER=deepgram` (requires `DEEPGRAM_API_KEY`)

TTS resilience options:
- `WORKER_TTS_FAIL_OPEN=true` keeps the session alive in text-fallback mode if ElevenLabs quota is low/unavailable
- `WORKER_TTS_MIN_REMAINING_CREDITS=25` minimum remaining ElevenLabs credits required to enable voice output
- Optional live voice fallback with Piper when ElevenLabs is exhausted:
	- `PIPER_TTS_ENABLED=true`
	- `PIPER_BINARY_PATH=piper`
	- `PIPER_MODEL_PATH=/models/en_US-amy-medium.onnx`
	- `PIPER_CONFIG_PATH=/models/en_US-amy-medium.onnx.json`
	- `WORKER_PIPER_SAMPLE_RATE=22050`

## Local Run

From repository root:

```bash
docker compose --profile voice up --build
```

Or run worker alone:

```bash
cd worker
pip install -r requirements.txt
python main.py start
```

## Notes

- The worker is intentionally isolated from the backend API process.
- Keep `WORKER_ROOM_PREFIX` aligned with backend `LIVEKIT_ROOM_PREFIX`.
- For stricter authz, set `WORKER_ALLOWED_IDENTITY_PREFIXES` (comma-separated).
- For Interviewer-v2 session IDs (`iv2s_*`), the worker asks the active backend question and submits spoken turns to Interviewer-v2 endpoints, instead of relying on generic LLM-only flow.
