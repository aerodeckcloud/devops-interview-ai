from __future__ import annotations

import os
import shutil
from typing import List
from pathlib import Path

from pydantic import ConfigDict, field_validator, model_validator
from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    WORKER_NAME: str = "ops-mentor-voice-worker"
    WORKER_AGENT_NAME: str = "ops-mentor-agent"
    WORKER_ROOM_PREFIX: str = "opsmentorai"
    WORKER_ALLOWED_IDENTITY_PREFIXES: str = ""

    WORKER_MAX_TURNS_PER_SESSION: int = 24
    WORKER_MAX_USER_MESSAGE_CHARS: int = 4000
    WORKER_MAX_ASSISTANT_CHARS: int = 1200
    WORKER_MIN_SECONDS_BETWEEN_TURNS: float = 0.8
    WORKER_RATE_LIMIT_WINDOW_SECONDS: int = 20
    WORKER_RATE_LIMIT_MAX_TURNS: int = 8
    WORKER_MAX_REFUSALS_PER_SESSION: int = 6
    WORKER_TELEMETRY_ENABLED: bool = True
    WORKER_ALERT_WEBHOOK_URL: str = ""

    WORKER_ENABLE_PROFANITY_FILTER: bool = True
    WORKER_ENABLE_PROMPT_INJECTION_FILTER: bool = True
    WORKER_ENABLE_OFF_TOPIC_FILTER: bool = True

    WORKER_BACKEND_API_BASE_URL: str = "http://backend:8000/api"
    WORKER_INTERNAL_API_KEY: str = ""

    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    WORKER_LLM_MODEL: str = "qwen/qwen3.8-27b"
    WORKER_LLM_TEMPERATURE: float = 0.3

    # auto: ElevenLabs when keys exist, otherwise Piper.
    # piper: local Piper only. elevenlabs: hosted voice, with Piper fallback when fail-open.
    WORKER_TTS_PROVIDER: str = "auto"
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    WORKER_TTS_FAIL_OPEN: bool = True
    WORKER_TTS_MIN_REMAINING_CREDITS: int = 25

    PIPER_TTS_ENABLED: bool = False
    PIPER_BINARY_PATH: str = "piper"
    PIPER_MODEL_PATH: str = ""
    PIPER_CONFIG_PATH: str = ""
    PIPER_SPEAKER_ID: int = 0
    PIPER_LENGTH_SCALE: float = 1.0
    PIPER_NOISE_SCALE: float = 0.667
    PIPER_NOISE_W: float = 0.8
    WORKER_PIPER_SAMPLE_RATE: int = 22050

    DEEPGRAM_API_KEY: str = ""
    WORKER_STT_PROVIDER: str = "openai"
    WORKER_STT_MODEL: str = "whisper-large-v3-turbo"
    WORKER_INTERVIEW_STYLE: str = "coaching"
    WORKER_MIN_INTERRUPTION_DURATION_SECONDS: float = 0.25
    WORKER_MIN_ENDPOINTING_DELAY_SECONDS: float = 0.25
    WORKER_MAX_ENDPOINTING_DELAY_SECONDS: float = 1.2
    WORKER_STRICT_MAX_RESPONSE_SENTENCES: int = 2
    WORKER_COACHING_MAX_RESPONSE_SENTENCES: int = 3

    model_config = ConfigDict(
        env_file=[
            os.path.join(os.path.dirname(__file__), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", ".env"),
        ],
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("WORKER_ROOM_PREFIX")
    @classmethod
    def validate_room_prefix(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("WORKER_ROOM_PREFIX must be set")
        return cleaned

    @field_validator("WORKER_LLM_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("WORKER_LLM_TEMPERATURE must be between 0 and 1")
        return value

    @field_validator("WORKER_INTERVIEW_STYLE")
    @classmethod
    def validate_interview_style(cls, value: str) -> str:
        normalized = (value or "coaching").strip().lower()
        if normalized not in {"coaching", "strict"}:
            raise ValueError("WORKER_INTERVIEW_STYLE must be one of: coaching, strict")
        return normalized

    @field_validator("WORKER_RATE_LIMIT_WINDOW_SECONDS", "WORKER_RATE_LIMIT_MAX_TURNS", "WORKER_MAX_REFUSALS_PER_SESSION")
    @classmethod
    def validate_positive_ints(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Rate limit and refusal settings must be >= 1")
        return value

    @field_validator("WORKER_STRICT_MAX_RESPONSE_SENTENCES", "WORKER_COACHING_MAX_RESPONSE_SENTENCES")
    @classmethod
    def validate_response_sentence_caps(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Response sentence limits must be >= 1")
        return value

    @field_validator("WORKER_TTS_MIN_REMAINING_CREDITS")
    @classmethod
    def validate_tts_min_credits(cls, value: int) -> int:
        if value < 0:
            raise ValueError("WORKER_TTS_MIN_REMAINING_CREDITS must be >= 0")
        return value

    @property
    def allowed_identity_prefixes(self) -> List[str]:
        prefixes = [item.strip() for item in (self.WORKER_ALLOWED_IDENTITY_PREFIXES or "").split(",")]
        return [prefix for prefix in prefixes if prefix]

    @property
    def has_livekit_config(self) -> bool:
        return bool(self.LIVEKIT_URL and self.LIVEKIT_API_KEY and self.LIVEKIT_API_SECRET)

    @property
    def has_stt(self) -> bool:
        provider = (self.WORKER_STT_PROVIDER or "").strip().lower()
        if provider == "deepgram":
            return bool(self.DEEPGRAM_API_KEY)
        if provider == "openai":
            return bool(self.GROQ_API_KEY)
        return False

    @property
    def tts_provider(self) -> str:
        choice = (self.WORKER_TTS_PROVIDER or "auto").strip().lower()
        if choice in {"auto", "piper", "elevenlabs"}:
            return choice
        return "auto"

    @property
    def has_tts(self) -> bool:
        if self.tts_provider == "piper":
            return self.has_piper_tts
        if self.tts_provider == "elevenlabs":
            return bool(self.ELEVENLABS_API_KEY and self.ELEVENLABS_VOICE_ID) or self.has_piper_tts
        if self.ELEVENLABS_API_KEY and self.ELEVENLABS_VOICE_ID:
            return True
        return self.has_piper_tts

    @property
    def has_piper_tts(self) -> bool:
        if not self.PIPER_TTS_ENABLED:
            return False
        model_path = Path((self.PIPER_MODEL_PATH or "").strip())
        if not model_path.exists():
            return False
        config_path = (self.PIPER_CONFIG_PATH or "").strip()
        if config_path and not Path(config_path).exists():
            return False
        binary = (self.PIPER_BINARY_PATH or "piper").strip()
        if not binary:
            return False
        if os.path.sep in binary:
            return Path(binary).exists()
        return bool(shutil.which(binary))

    @property
    def has_llm(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def has_backend_access(self) -> bool:
        return bool((self.WORKER_BACKEND_API_BASE_URL or "").strip() and (self.WORKER_INTERNAL_API_KEY or "").strip())

    @model_validator(mode="after")
    def validate_required_secrets(self):
        if not self.has_livekit_config:
            raise ValueError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be configured")
        if not self.has_stt:
            provider = (self.WORKER_STT_PROVIDER or "").strip().lower() or "unknown"
            if provider == "deepgram":
                raise ValueError("DEEPGRAM_API_KEY must be configured when WORKER_STT_PROVIDER=deepgram")
            if provider == "openai":
                raise ValueError("GROQ_API_KEY must be configured when WORKER_STT_PROVIDER=openai")
            raise ValueError("WORKER_STT_PROVIDER must be one of: openai, deepgram")
        if not self.has_tts:
            raise ValueError(
                "TTS is not configured. Provide ELEVENLABS_API_KEY+ELEVENLABS_VOICE_ID or enable Piper with valid model/binary."
            )
        if not self.has_llm:
            raise ValueError("GROQ_API_KEY must be configured for LLM responses")
        if not self.has_backend_access:
            raise ValueError("WORKER_BACKEND_API_BASE_URL and WORKER_INTERNAL_API_KEY must be configured")
        return self


worker_settings = WorkerSettings()
