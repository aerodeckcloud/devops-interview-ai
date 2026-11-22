import re
import uuid
from typing import Optional, Tuple
from datetime import timedelta
import logging
import json
import asyncio

from config import settings

try:
    from livekit import api as livekit_api
except ImportError:  # pragma: no cover
    livekit_api = None


class LiveKitService:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def _sanitize_identity(self, raw_identity: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_identity or "")
        cleaned = re.sub(r"-+", "-", cleaned).strip("-")
        return cleaned[:128] or f"anon-{uuid.uuid4().hex[:8]}"

    def _sanitize_room_name(self, raw_name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", raw_name or "")
        cleaned = re.sub(r"-+", "-", cleaned).strip("-")
        return cleaned[:128] or f"{settings.LIVEKIT_ROOM_PREFIX}-room"

    def is_enabled(self) -> bool:
        return bool(settings.VOICE_AGENT_RUNTIME_ENABLED)

    def server_url(self) -> str:
        return (settings.LIVEKIT_INTERNAL_URL or settings.LIVEKIT_URL or "").strip()

    def is_configured(self) -> bool:
        return bool(
            settings.LIVEKIT_URL
            and settings.LIVEKIT_API_KEY
            and settings.LIVEKIT_API_SECRET
        )

    def get_runtime_status(self) -> dict:
        return {
            "enabled": self.is_enabled(),
            "provider": settings.VOICE_PROVIDER,
            "configured": self.is_configured(),
            "livekit_url": settings.LIVEKIT_URL or None,
            "agent_name": settings.LIVEKIT_AGENT_NAME,
            "auto_dispatch": bool(settings.LIVEKIT_AUTO_DISPATCH),
        }

    async def ensure_worker_dispatch(
        self,
        room_name: str,
        session_id: str,
        identity: str,
        interviewer_style: Optional[str] = None,
        interruption_profile: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        if not settings.LIVEKIT_AUTO_DISPATCH:
            return False, "auto_dispatch_disabled"
        if livekit_api is None:
            return False, "livekit_api_missing"
        if not settings.LIVEKIT_AGENT_NAME:
            return False, "agent_name_not_configured"

        if not self.is_configured():
            return False, "livekit_not_configured"

        request_cls = getattr(livekit_api, "CreateAgentDispatchRequest", None)
        api_cls = getattr(livekit_api, "LiveKitAPI", None)
        if request_cls is None or api_cls is None:
            return False, "dispatch_api_unavailable"

        metadata = json.dumps(
            {
                "session_id": session_id,
                "room_name": room_name,
                "candidate_identity": identity,
                "interviewer_style": (interviewer_style or "coaching"),
                "interruption_profile": (interruption_profile or "balanced"),
            }
        )

        max_retries = max(1, int(settings.LIVEKIT_DISPATCH_MAX_RETRIES))
        initial_backoff = max(0.0, float(settings.LIVEKIT_DISPATCH_INITIAL_BACKOFF_SECONDS))
        max_backoff = max(initial_backoff, float(settings.LIVEKIT_DISPATCH_MAX_BACKOFF_SECONDS))
        multiplier = max(1.0, float(settings.LIVEKIT_DISPATCH_BACKOFF_MULTIPLIER))

        attempt = 0
        while attempt < max_retries:
            client = None
            try:
                client = api_cls(
                    url=self.server_url(),
                    api_key=settings.LIVEKIT_API_KEY,
                    api_secret=settings.LIVEKIT_API_SECRET,
                )

                request = request_cls(
                    room=room_name,
                    agent_name=settings.LIVEKIT_AGENT_NAME,
                    metadata=metadata,
                )
                await client.agent_dispatch.create_dispatch(request)
                return True, None
            except Exception as exc:
                attempt += 1
                self.logger.warning(
                    "LiveKit worker dispatch failed for room=%s attempt=%s/%s: %s",
                    room_name,
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt >= max_retries:
                    return False, "dispatch_failed"

                backoff_seconds = min(max_backoff, initial_backoff * (multiplier ** (attempt - 1)))
                await asyncio.sleep(backoff_seconds)
            finally:
                if client is not None:
                    try:
                        await client.aclose()
                    except Exception:
                        pass

        return False, "dispatch_failed"

    def issue_session_token(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        room_name: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Tuple[str, str, str, int]:
        if not self.is_enabled():
            raise RuntimeError("Voice agent runtime is disabled")
        if settings.VOICE_PROVIDER != "livekit":
            raise RuntimeError(f"Unsupported voice provider: {settings.VOICE_PROVIDER}")
        if not self.is_configured():
            raise RuntimeError("LiveKit is not fully configured")
        if livekit_api is None:
            raise RuntimeError("livekit-api dependency is not installed")

        room_seed = room_name or f"{settings.LIVEKIT_ROOM_PREFIX}-{session_id}"
        resolved_room_name = self._sanitize_room_name(room_seed)
        base_identity = f"candidate-{user_id}" if user_id else f"anon-{uuid.uuid4().hex[:8]}"
        identity = self._sanitize_identity(base_identity)
        token_name = display_name or identity

        grants = livekit_api.VideoGrants(
            room_join=True,
            room=resolved_room_name,
            can_publish=True,
            can_subscribe=True,
        )

        access_token = (
            livekit_api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            .with_identity(identity)
            .with_name(token_name)
            .with_grants(grants)
            .with_ttl(timedelta(seconds=settings.LIVEKIT_TOKEN_TTL_SECONDS))
        )
        jwt_token = access_token.to_jwt()

        return jwt_token, resolved_room_name, identity, settings.LIVEKIT_TOKEN_TTL_SECONDS


livekit_service = LiveKitService()
