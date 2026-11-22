# Ops Mentor AI review guide

This file is the project guide for Cursor Bugbot. Bugbot includes it on every pull request review. Treat a missed item here as a bug, not a style note.

## Pull requests

- Every pull request must be reviewed by Cursor Bugbot before merge. Comment `cursor review` or `bugbot run` if a review did not start.
- Do not merge while a Bugbot finding on this guide is unresolved.

## Launch safety

- Groq, exam, speech, TTS synthesis, journey generation, and LiveKit token routes require a logged-in user. Check `user_id` before reading or writing a session, exam, or artifact.
- Registration must leave `is_admin` false. Admin comes only from `backend/create_admin.py`.
- Production (`ENVIRONMENT` of production or staging) must refuse to boot when `DEBUG` is true, `COOKIE_SECURE` is false, `ALLOWED_ORIGINS` is empty or `*`, the JWT secret is a placeholder or shorter than 32 characters, or `GROQ_API_KEY` is missing.
- HTTP 500 responses stay generic. Log the exception on the server. Do not return driver errors, stack traces, file paths, or secrets.
- Compare worker and other shared secrets with `hmac.compare_digest`.
- Do not commit `.env` files, API keys, LiveKit dev key pairs, or MongoDB passwords.
- MongoDB stays off the public interface. Production compose publishes 80 and 443 only.

## Voice

- `deploy/livekit.yaml` dev keys and `node_ip: 127.0.0.1` are local-only. A change that publishes them for a public droplet is a bug unless it also replaces the key pair and sets a public WebRTC address.
