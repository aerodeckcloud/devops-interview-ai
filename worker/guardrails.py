from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


PROMPT_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore above",
    "system prompt",
    "developer prompt",
    "jailbreak",
    "act as",
    "reveal instructions",
)

OFF_TOPIC_PATTERNS = (
    "tell me a joke",
    "movie",
    "politics",
    "celebrity",
    "crypto price",
    "sports",
)

PROFANITY_PATTERNS = (
    "fuck",
    "shit",
    "bitch",
    "asshole",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


@dataclass
class GuardrailDecision:
    allowed: bool
    reason: Optional[str] = None
    message: Optional[str] = None


class VoiceGuardrails:
    def __init__(
        self,
        *,
        max_user_chars: int,
        max_assistant_chars: int,
        enable_prompt_injection_filter: bool,
        enable_off_topic_filter: bool,
        enable_profanity_filter: bool,
    ) -> None:
        self.max_user_chars = max_user_chars
        self.max_assistant_chars = max_assistant_chars
        self.enable_prompt_injection_filter = enable_prompt_injection_filter
        self.enable_off_topic_filter = enable_off_topic_filter
        self.enable_profanity_filter = enable_profanity_filter

    def evaluate_user_message(self, message: str) -> GuardrailDecision:
        text = (message or "").strip()
        if not text:
            return GuardrailDecision(
                allowed=False,
                reason="empty_user_message",
                message="Please provide your interview answer so we can continue.",
            )

        if len(text) > self.max_user_chars:
            return GuardrailDecision(
                allowed=False,
                reason="message_too_long",
                message="Your response is too long for one turn. Please summarize in under 4,000 characters.",
            )

        lowered = _normalize(text)

        if self.enable_prompt_injection_filter and any(p in lowered for p in PROMPT_INJECTION_PATTERNS):
            return GuardrailDecision(
                allowed=False,
                reason="prompt_injection_attempt",
                message="I can’t help with instruction bypass attempts. Please answer the interview question directly.",
            )

        if self.enable_off_topic_filter and any(p in lowered for p in OFF_TOPIC_PATTERNS):
            return GuardrailDecision(
                allowed=False,
                reason="off_topic_request",
                message="Let’s stay focused on your DevOps interview scenario.",
            )

        if self.enable_profanity_filter and any(p in lowered for p in PROFANITY_PATTERNS):
            return GuardrailDecision(
                allowed=False,
                reason="unsafe_language",
                message="Please keep responses professional and interview-focused.",
            )

        return GuardrailDecision(allowed=True)

    def sanitize_assistant_message(self, message: str) -> str:
        text = (message or "").strip()
        if not text:
            return "Please continue with your answer and include architecture choices, risks, and validation steps."

        text = re.sub(r"\b(api[_\s-]?key|secret|token|password|private key)\b", "[redacted]", text, flags=re.IGNORECASE)

        if len(text) > self.max_assistant_chars:
            return text[: self.max_assistant_chars - 3].rstrip() + "..."

        return text
