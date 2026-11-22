import os
from typing import List

from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Environment
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True

    # Groq Settings
    GROQ_API_KEY: str = ""  # Will be loaded from .env file
    GROQ_MODEL: str = "qwen/qwen3.8-27b"  # Current Groq chat model (llama-3.1-8b-instant was removed)
    GROQ_TEMPERATURE: float = 0.7
    GROQ_MAX_TOKENS: int = 2048

    # JWT Authentication Settings
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_PREVIOUS_SECRET_KEYS: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ISSUER: str = "ops-mentor-ai"
    JWT_AUDIENCE: str = "ops-mentor-ai-users"

    # Auth Cookies
    ACCESS_COOKIE_NAME: str = "opsmentorai_access"
    REFRESH_COOKIE_NAME: str = "opsmentorai_refresh"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str = ""

    # Verification & Reset Tokens
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Database Settings (MongoDB)
    MONGODB_URI: str = "mongodb://localhost:27017/ops_mentor_ai"
    MONGODB_DB_NAME: str = "ops_mentor_ai"

    # Speech Settings
    WHISPER_MODEL: str = "base"  # tiny, base, small, medium, large

    # ElevenLabs TTS Settings
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    WORKER_TTS_MIN_REMAINING_CREDITS: int = 25
    ELEVENLABS_STABILITY: float = 0.5
    ELEVENLABS_SIMILARITY: float = 0.75
    TTS_CACHE_ENABLED: bool = True
    TTS_CACHE_TTL_SECONDS: int = 604800
    TTS_CACHE_MAX_FILES: int = 500

    # auto uses ElevenLabs when configured, otherwise Piper.
    # piper forces the local Piper voice. elevenlabs forces the hosted voice.
    TTS_PROVIDER: str = "auto"

    # Piper TTS fallback settings
    PIPER_TTS_ENABLED: bool = False
    PIPER_BINARY_PATH: str = "piper"
    PIPER_MODEL_PATH: str = ""
    PIPER_CONFIG_PATH: str = ""
    PIPER_SPEAKER_ID: int = 0
    PIPER_LENGTH_SCALE: float = 1.0
    PIPER_NOISE_SCALE: float = 0.667
    PIPER_NOISE_W: float = 0.8

    # Interview Settings
    MAX_QUESTION_COUNT: int = 10
    SESSION_TIMEOUT: int = 3600  # 1 hour in seconds

    # Voice Agent Runtime (LiveKit migration)
    VOICE_AGENT_RUNTIME_ENABLED: bool = False
    VOICE_PROVIDER: str = "livekit"
    LIVEKIT_URL: str = ""
    # Server-side LiveKit API address. Use this when the browser URL
    # (LIVEKIT_URL) differs from the address containers use, for example
    # ws://127.0.0.1:7880 for the browser and ws://livekit:7880 for dispatch.
    LIVEKIT_INTERNAL_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    LIVEKIT_TOKEN_TTL_SECONDS: int = 3600
    LIVEKIT_ROOM_PREFIX: str = "opsmentorai"
    LIVEKIT_AGENT_NAME: str = "ops-mentor-agent"
    LIVEKIT_AUTO_DISPATCH: bool = True
    LIVEKIT_DISPATCH_MAX_RETRIES: int = 3
    LIVEKIT_DISPATCH_INITIAL_BACKOFF_SECONDS: float = 0.4
    LIVEKIT_DISPATCH_MAX_BACKOFF_SECONDS: float = 3.0
    LIVEKIT_DISPATCH_BACKOFF_MULTIPLIER: float = 2.0
    WORKER_INTERNAL_API_KEY: str = ""

    # Storage
    AUDIO_UPLOAD_DIR: str = "./uploads/audio"
    AVATAR_UPLOAD_DIR: str = "./uploads/avatars"
    SESSION_RECORD_DIR: str = "./sessions"

    model_config = ConfigDict(
        env_file=[
            os.path.join(os.path.dirname(__file__), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        ],
        case_sensitive=True,
        extra="ignore",
        protected_namespaces=(),
    )

    @staticmethod
    def _is_placeholder_secret(value: str) -> bool:
        candidate = (value or "").strip().lower()
        placeholders = {
            "",
            "change-me-in-production",
            "your_jwt_secret_key_here",
            "your-secret-key",
            "secret",
            "jwt_secret",
            "default",
            "changeme",
        }
        return candidate in placeholders or candidate.startswith("your_")

    @property
    def is_production(self) -> bool:
        env = (self.ENVIRONMENT or "").strip().lower()
        return (not self.DEBUG) or env in {"prod", "production", "staging"}

    @property
    def jwt_previous_secret_keys(self) -> List[str]:
        raw = (self.JWT_PREVIOUS_SECRET_KEYS or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_jwt_security(self):
        secret = (self.JWT_SECRET_KEY or "").strip()
        if not secret:
            raise ValueError("JWT_SECRET_KEY must be set")

        if self._is_placeholder_secret(secret):
            if self.is_production:
                raise ValueError(
                    "JWT_SECRET_KEY uses a placeholder value. Set a strong random secret before running in production."
                )
            return self

        if self.is_production and len(secret) < 32:
            raise ValueError(
                "JWT_SECRET_KEY is too short for production. Use at least 32 characters (48+ recommended)."
            )

        for old_key in self.jwt_previous_secret_keys:
            if old_key == secret:
                raise ValueError("JWT_PREVIOUS_SECRET_KEYS must not include the current JWT_SECRET_KEY")

        return self

settings = Settings()

# Create necessary directories
os.makedirs(settings.AUDIO_UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.AVATAR_UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.SESSION_RECORD_DIR, exist_ok=True)
