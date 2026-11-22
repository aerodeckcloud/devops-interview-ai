import httpx
import hashlib
import time
import asyncio
import os
import shutil
import tempfile

from typing import Optional, Dict, Tuple
from pathlib import Path
from elevenlabs.client import ElevenLabs
from config import settings


class TextToSpeechService:
    def __init__(self) -> None:
        self.api_key = settings.ELEVENLABS_API_KEY
        self.default_voice_id = settings.ELEVENLABS_VOICE_ID
        self.model_id = settings.ELEVENLABS_MODEL_ID
        self.elevenlabs_available = bool(self.api_key)
        self.client = ElevenLabs(api_key=self.api_key) if self.elevenlabs_available else None
        self.piper_enabled = bool(settings.PIPER_TTS_ENABLED)
        self.piper_binary_path = (settings.PIPER_BINARY_PATH or "piper").strip()
        self.piper_model_path = (settings.PIPER_MODEL_PATH or "").strip()
        self.piper_config_path = (settings.PIPER_CONFIG_PATH or "").strip()
        self.piper_speaker_id = int(settings.PIPER_SPEAKER_ID)
        self.piper_length_scale = float(settings.PIPER_LENGTH_SCALE)
        self.piper_noise_scale = float(settings.PIPER_NOISE_SCALE)
        self.piper_noise_w = float(settings.PIPER_NOISE_W)
        self.available = self.elevenlabs_available or self._is_piper_configured()
        self._active_provider = "elevenlabs" if self.elevenlabs_available else ("piper" if self._is_piper_configured() else "none")
        self.cache_enabled = settings.TTS_CACHE_ENABLED
        self.cache_ttl_seconds = max(0, settings.TTS_CACHE_TTL_SECONDS)
        self.cache_max_files = max(0, settings.TTS_CACHE_MAX_FILES)
        self.cache_dir = Path(settings.AUDIO_UPLOAD_DIR) / "tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_writes = 0
        self.cache_evictions = 0
        self.provider_status_ttl_seconds = 60
        self._provider_status_checked_at = 0.0
        self._provider_ready = False
        self._provider_reason: Optional[str] = None
        self._subscription_checked_at = 0.0
        self._remaining_credits: Optional[int] = None
        self._subscription_reason: Optional[str] = None

    @property
    def active_provider(self) -> str:
        return self._active_provider

    def _preferred_provider(self) -> str:
        choice = (getattr(settings, "TTS_PROVIDER", "auto") or "auto").strip().lower()
        if choice in {"piper", "elevenlabs", "auto"}:
            return choice
        return "auto"

    def _is_piper_configured(self) -> bool:
        return bool(self.piper_enabled and self.piper_model_path)

    def _check_piper_health(self) -> Tuple[bool, Optional[str]]:
        if not self._is_piper_configured():
            return False, "piper_not_configured"

        model_path = Path(self.piper_model_path)
        if not model_path.exists():
            return False, "piper_model_missing"

        if self.piper_config_path and not Path(self.piper_config_path).exists():
            return False, "piper_config_missing"

        binary_exists = Path(self.piper_binary_path).exists() if os.path.sep in self.piper_binary_path else bool(shutil.which(self.piper_binary_path))
        if not binary_exists:
            return False, "piper_binary_missing"

        return True, None

    async def check_provider_health(self, force: bool = False) -> Tuple[bool, Optional[str]]:
        self.available = self.elevenlabs_available or self._is_piper_configured()
        if not self.available:
            self._provider_ready = False
            self._provider_reason = "api_key_missing"
            self._active_provider = "none"
            self._provider_status_checked_at = time.time()
            return self._provider_ready, self._provider_reason

        now = time.time()
        if (
            not force
            and self._provider_status_checked_at > 0
            and (now - self._provider_status_checked_at) < self.provider_status_ttl_seconds
        ):
            return self._provider_ready, self._provider_reason

        preferred = self._preferred_provider()
        if preferred == "piper":
            piper_ready, piper_reason = self._check_piper_health()
            self._provider_ready = piper_ready
            self._provider_reason = None if piper_ready else piper_reason
            self._active_provider = "piper" if piper_ready else "none"
            self._provider_status_checked_at = time.time()
            return self._provider_ready, self._provider_reason

        elevenlabs_reason: Optional[str] = None
        elevenlabs_ready = False

        if self.elevenlabs_available and preferred != "piper":
            headers = {
                "xi-api-key": self.api_key,
            }

            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    response = await client.get("https://api.elevenlabs.io/v1/user", headers=headers)

                if response.status_code == 200:
                    elevenlabs_ready = True
                    elevenlabs_reason = None
                elif response.status_code == 401:
                    reason = "invalid_api_key"
                    try:
                        payload = response.json() if response.content else {}
                        detail = payload.get("detail") if isinstance(payload, dict) else None
                        if isinstance(detail, dict):
                            status_code = str(detail.get("status") or "").strip().lower()
                            message = str(detail.get("message") or "").strip().lower()
                            if status_code == "missing_permissions":
                                if "user_read" in message:
                                    reason = "missing_permission_user_read"
                                else:
                                    reason = "missing_permissions"
                    except Exception:
                        pass
                    elevenlabs_reason = reason
                elif response.status_code == 429:
                    elevenlabs_reason = "rate_limited"
                else:
                    elevenlabs_reason = f"provider_http_{response.status_code}"
            except httpx.TimeoutException:
                elevenlabs_reason = "provider_timeout"
            except Exception:
                elevenlabs_reason = "provider_unreachable"
        else:
            elevenlabs_reason = "api_key_missing"

        if elevenlabs_ready:
            self._provider_ready = True
            self._provider_reason = None
            self._active_provider = "elevenlabs"
            self._provider_status_checked_at = time.time()
            return self._provider_ready, self._provider_reason

        piper_ready, piper_reason = self._check_piper_health()
        if piper_ready:
            self._provider_ready = True
            self._provider_reason = "using_piper_fallback" if self.elevenlabs_available and elevenlabs_reason else None
            self._active_provider = "piper"
            self._provider_status_checked_at = time.time()
            return self._provider_ready, self._provider_reason

        self._provider_ready = False
        self._provider_reason = elevenlabs_reason or piper_reason or "provider_unavailable"
        self._active_provider = "none"

        self._provider_status_checked_at = time.time()
        return self._provider_ready, self._provider_reason

    async def get_subscription_status(self, force: bool = False) -> Tuple[Optional[int], Optional[str]]:
        if not self.elevenlabs_available:
            if self._is_piper_configured():
                self._remaining_credits = None
                self._subscription_reason = "not_applicable_piper"
                self._subscription_checked_at = time.time()
                return self._remaining_credits, self._subscription_reason
            self._remaining_credits = None
            self._subscription_reason = "api_key_missing"
            self._subscription_checked_at = time.time()
            return self._remaining_credits, self._subscription_reason

        if self.active_provider == "piper":
            self._remaining_credits = None
            self._subscription_reason = "not_applicable_piper"
            self._subscription_checked_at = time.time()
            return self._remaining_credits, self._subscription_reason

        now = time.time()
        if (
            not force
            and self._subscription_checked_at > 0
            and (now - self._subscription_checked_at) < self.provider_status_ttl_seconds
        ):
            return self._remaining_credits, self._subscription_reason

        headers = {
            "xi-api-key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get("https://api.elevenlabs.io/v1/user/subscription", headers=headers)

            if response.status_code == 200:
                payload = response.json() if response.content else {}
                character_count = int(payload.get("character_count") or 0) if isinstance(payload, dict) else 0
                character_limit = int(payload.get("character_limit") or 0) if isinstance(payload, dict) else 0
                if character_limit > 0:
                    self._remaining_credits = max(character_limit - character_count, 0)
                else:
                    self._remaining_credits = None
                self._subscription_reason = None
            elif response.status_code == 401:
                self._remaining_credits = None
                self._subscription_reason = "invalid_api_key"
            elif response.status_code == 429:
                self._remaining_credits = None
                self._subscription_reason = "rate_limited"
            else:
                self._remaining_credits = None
                self._subscription_reason = f"provider_http_{response.status_code}"
        except httpx.TimeoutException:
            self._remaining_credits = None
            self._subscription_reason = "provider_timeout"
        except Exception:
            self._remaining_credits = None
            self._subscription_reason = "provider_unreachable"

        self._subscription_checked_at = time.time()
        return self._remaining_credits, self._subscription_reason

    def apply_runtime_config(self, runtime_config: Optional[Dict] = None) -> None:
        config = runtime_config or {}
        self.default_voice_id = config.get("tts_default_voice_id") or settings.ELEVENLABS_VOICE_ID
        self.model_id = config.get("tts_model_id") or settings.ELEVENLABS_MODEL_ID
        self.cache_enabled = bool(config.get("tts_cache_enabled", settings.TTS_CACHE_ENABLED))
        self.cache_ttl_seconds = max(0, int(config.get("tts_cache_ttl_seconds", settings.TTS_CACHE_TTL_SECONDS)))
        self.cache_max_files = max(0, int(config.get("tts_cache_max_files", settings.TTS_CACHE_MAX_FILES)))

    def clear_cache(self) -> int:
        removed = 0
        for file_path in self._cache_files():
            try:
                file_path.unlink(missing_ok=True)
                removed += 1
            except Exception:
                continue
        return removed

    def _cache_files(self):
        return [path for path in self.cache_dir.glob("*") if path.is_file() and path.suffix.lower() in {".mp3", ".wav"}]

    def _cleanup_cache(self) -> None:
        if not self.cache_enabled:
            return 0

        try:
            files = self._cache_files()
        except Exception:
            return 0

        now = time.time()
        active_files = []
        removed_count = 0
        for file_path in files:
            try:
                modified = file_path.stat().st_mtime
                if self.cache_ttl_seconds > 0 and (now - modified) > self.cache_ttl_seconds:
                    file_path.unlink(missing_ok=True)
                    removed_count += 1
                else:
                    active_files.append(file_path)
            except Exception:
                continue

        if self.cache_max_files > 0 and len(active_files) > self.cache_max_files:
            active_files.sort(key=lambda p: p.stat().st_mtime)
            remove_count = len(active_files) - self.cache_max_files
            for file_path in active_files[:remove_count]:
                try:
                    file_path.unlink(missing_ok=True)
                    removed_count += 1
                except Exception:
                    continue

        if removed_count > 0:
            self.cache_evictions += removed_count

        return removed_count

    def _build_cache_key(
        self,
        text: str,
        provider: str,
        voice_id: str,
        stability: Optional[float],
        similarity_boost: Optional[float],
    ) -> str:
        payload = "|".join(
            [
                provider or "",
                self.model_id or "",
                voice_id or "",
                "" if stability is None else f"{stability:.3f}",
                "" if similarity_boost is None else f"{similarity_boost:.3f}",
                text,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def list_voices(self):
        if self.active_provider == "piper":
            model_name = Path(self.piper_model_path).name or "piper"
            return [
                {
                    "voice_id": "piper-default",
                    "name": f"Piper ({model_name})",
                    "category": "local",
                    "description": "Local Piper fallback voice",
                    "labels": {"provider": "piper"},
                }
            ]

        if not self.elevenlabs_available:
            raise RuntimeError("No TTS provider is configured.")

        headers = {
            "xi-api-key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://api.elevenlabs.io/v1/voices", headers=headers)
            response.raise_for_status()

        data = response.json()
        voices = data.get("voices", []) if isinstance(data, dict) else []
        return [
            {
                "voice_id": voice.get("voice_id"),
                "name": voice.get("name"),
                "category": voice.get("category"),
                "description": voice.get("description"),
                "labels": voice.get("labels") or {},
            }
            for voice in voices
            if voice.get("voice_id")
        ]

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        stability: Optional[float] = None,
        similarity_boost: Optional[float] = None,
    ):
        if not self.available:
            raise RuntimeError("No TTS provider is configured.")

        preferred = self._preferred_provider()
        if preferred == "piper" or (preferred == "auto" and not self.elevenlabs_available):
            provider = "piper"
        else:
            provider = "elevenlabs"
        resolved_voice_id = voice_id or self.default_voice_id
        if provider == "elevenlabs" and not resolved_voice_id:
            raise RuntimeError("ElevenLabs voice id is not configured.")

        cache_key = self._build_cache_key(
            text=text,
            provider=provider,
            voice_id=resolved_voice_id or "piper-default",
            stability=stability,
            similarity_boost=similarity_boost,
        )
        cache_extension = ".mp3" if provider == "elevenlabs" else ".wav"
        cache_file = self.cache_dir / f"{cache_key}{cache_extension}"
        self._cleanup_cache()
        if self.cache_enabled and cache_file.exists() and cache_file.stat().st_size > 0:
            self.cache_hits += 1
            cache_file.touch(exist_ok=True)
            return cache_file.read_bytes(), "audio/mpeg" if cache_extension == ".mp3" else "audio/wav"
        self.cache_misses += 1

        audio_bytes = b""
        content_type = "audio/mpeg"

        if provider == "elevenlabs":
            voice_settings = None
            if stability is not None or similarity_boost is not None:
                voice_settings = {
                    "stability": stability if stability is not None else settings.ELEVENLABS_STABILITY,
                    "similarity_boost": similarity_boost if similarity_boost is not None else settings.ELEVENLABS_SIMILARITY,
                }

            try:
                audio = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=resolved_voice_id,
                    model_id=self.model_id,
                    output_format="mp3_44100_128",
                    optimize_streaming_latency=0,
                    voice_settings=voice_settings,
                )

                if isinstance(audio, bytes):
                    audio_bytes = audio
                else:
                    audio_bytes = b"".join(chunk for chunk in audio)
                content_type = "audio/mpeg"
            except Exception:
                piper_ready, _reason = self._check_piper_health()
                if not piper_ready:
                    raise
                provider = "piper"
                cache_extension = ".wav"
                cache_file = self.cache_dir / f"{cache_key}{cache_extension}"
                audio_bytes, content_type = await self._synthesize_with_piper(text)
        else:
            audio_bytes, content_type = await self._synthesize_with_piper(text)

        if self.cache_enabled and audio_bytes:
            cache_file.write_bytes(audio_bytes)
            self.cache_writes += 1
            self._cleanup_cache()

        return audio_bytes, content_type

    async def _synthesize_with_piper(self, text: str) -> Tuple[bytes, str]:
        piper_ready, piper_reason = self._check_piper_health()
        if not piper_ready:
            raise RuntimeError(f"Piper not ready: {piper_reason}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            output_path = tmp_file.name

        command = [
            self.piper_binary_path,
            "--model",
            self.piper_model_path,
            "--output_file",
            output_path,
            "--length_scale",
            str(self.piper_length_scale),
            "--noise_scale",
            str(self.piper_noise_scale),
            "--noise_w",
            str(self.piper_noise_w),
        ]
        if self.piper_config_path:
            command.extend(["--config", self.piper_config_path])
        if self.piper_speaker_id >= 0:
            command.extend(["--speaker", str(self.piper_speaker_id)])

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, stderr = await process.communicate(input=(text or "").encode("utf-8"))
            if process.returncode != 0:
                detail = (stderr or b"").decode("utf-8", errors="ignore").strip()
                raise RuntimeError(f"Piper synthesis failed ({process.returncode}): {detail[:220]}")

            audio_bytes = Path(output_path).read_bytes()
            if not audio_bytes:
                raise RuntimeError("Piper synthesis returned empty audio")
            self._active_provider = "piper"
            return audio_bytes, "audio/wav"
        finally:
            try:
                Path(output_path).unlink(missing_ok=True)
            except Exception:
                pass

    def get_cache_stats(self) -> Dict:
        try:
            files = self._cache_files()
            file_count = len(files)
            size_bytes = sum(path.stat().st_size for path in files)
        except Exception:
            file_count = 0
            size_bytes = 0

        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests) if total_requests > 0 else 0.0

        return {
            "enabled": self.cache_enabled,
            "ttl_seconds": self.cache_ttl_seconds,
            "max_files": self.cache_max_files,
            "file_count": file_count,
            "size_bytes": size_bytes,
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "writes": self.cache_writes,
            "evictions": self.cache_evictions,
            "hit_rate": hit_rate,
        }


tts_service = TextToSpeechService()
