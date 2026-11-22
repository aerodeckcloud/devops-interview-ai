from __future__ import annotations

from typing import Dict, Optional


DERAILMENT_PATTERNS = [
    "ignore previous",
    "ignore above",
    "jailbreak",
    "system prompt",
    "developer prompt",
    "act as",
    "roleplay",
    "tell me a joke",
    "weather",
    "movie",
    "politics",
    "write code for",
    "teach me",
    "how to answer",
    "give me the answer",
    "answer this for me",
    "can you answer",
    "what is your name",
    "who are you",
]

QUESTION_CONTROL_PATTERNS = [
    "repeat the question",
    "can you repeat",
    "say that again",
    "repeat that",
    "what was the question",
    "what is the question",
    "can you clarify",
    "clarify the question",
    "can you continue",
    "continue please",
    "follow up question",
    "i didn't say anything",
    "i did not say anything",
    "can you hear me",
    "did you get me",
    "hello",
]

UNCERTAINTY_RESPONSE_PATTERNS = [
    "i don't think i know",
    "i dont think i know",
    "i don't know",
    "i dont know",
    "not sure",
    "i am not sure",
    "i'm not sure",
    "i do not know",
    "i have no idea",
    "not certain",
    "unsure",
    "i'm stuck",
    "i am stuck",
]

PARTIAL_ATTEMPT_PATTERNS = [
    "i think",
    "i would",
    "maybe",
    "my approach",
    "i'd start",
    "i would start",
    "first i",
]


def _normalize_tokens(text: str):
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in (text or ""))
    return [token for token in cleaned.split() if len(token) > 2]


def _has_any_pattern(text: str, patterns: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(pattern in lowered for pattern in patterns)


class InterviewPolicyService:
    def evaluate_user_response(
        self,
        user_response: str,
        active_question: Optional[str],
        strict_mode: bool,
    ) -> Dict:
        text = (user_response or "").strip()

        if not text:
            return {
                "allowed": False,
                "reason": "empty_response",
                "message": self._refusal_message(active_question),
            }

        if strict_mode:
            lowered = text.lower()

            # Keep interview flow natural: allow question-control requests.
            for pattern in QUESTION_CONTROL_PATTERNS:
                if pattern in lowered:
                    if active_question:
                        return {
                            "allowed": False,
                            "reason": "question_control_intent",
                            "message": f"Sure. Here is the current question again: {active_question}",
                        }
                    return {
                        "allowed": False,
                        "reason": "question_control_intent",
                        "message": "Sure. Please answer the active interview question and I will continue.",
                    }

            for pattern in DERAILMENT_PATTERNS:
                if pattern in lowered:
                    return {
                        "allowed": False,
                        "reason": "out_of_scope_or_role_switch_attempt",
                        "message": self._refusal_message(active_question),
                    }

            # Treat uncertainty as a legitimate interview response intent, not a refusal.
            # The scoring layer will naturally produce a low score and coach the candidate.
            if _has_any_pattern(lowered, UNCERTAINTY_RESPONSE_PATTERNS):
                return {
                    "allowed": True,
                    "reason": "uncertainty_response_allowed",
                    "message": None,
                }

            if active_question:
                question_tokens = set(_normalize_tokens(active_question))
                answer_tokens = _normalize_tokens(text)
                overlap = len(question_tokens.intersection(set(answer_tokens)))
                # Allow short but clearly-attempted answers even with low lexical overlap.
                short_attempt = len(answer_tokens) < 8 and _has_any_pattern(lowered, PARTIAL_ATTEMPT_PATTERNS)
                if len(answer_tokens) < 8 and overlap == 0 and not short_attempt:
                    return {
                        "allowed": False,
                        "reason": "response_needs_clarification",
                        "message": (
                            f"I may have misheard that. Let’s continue with the current question: {active_question}"
                            if active_question
                            else "I may have misheard that. Please answer the active interview question."
                        ),
                    }

        return {
            "allowed": True,
            "reason": None,
            "message": None,
        }

    @staticmethod
    def _refusal_message(active_question: Optional[str]) -> str:
        if active_question:
            return (
                "I can’t help with that during this interview. Let’s stay focused. "
                f"Please answer the current question: {active_question}"
            )
        return "I can’t help with that during this interview. Let’s stay focused."


interview_policy_service = InterviewPolicyService()
