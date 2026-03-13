"""Prompt injection defense: rule-based filtering and NPC-specific rejection responses."""

from __future__ import annotations

import logging
import re

from src.npc.intent import SecurityLevel

logger = logging.getLogger(__name__)


# Regex patterns for detecting prompt injection attempts (Korean + English)
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # English injection patterns
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"ignore\s+above", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+)?", re.IGNORECASE),
    re.compile(r"pretend\s+(to\s+be|you\s+are)", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?instructions", re.IGNORECASE),
    re.compile(r"show\s+(me\s+)?(your\s+)?prompt", re.IGNORECASE),
    re.compile(r"what\s+are\s+your\s+instructions", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|filter|guard)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
    re.compile(r"developer\s+mode", re.IGNORECASE),

    # Korean injection patterns
    re.compile(r"시스템\s*프롬프트", re.IGNORECASE),
    re.compile(r"이전\s*지시(를)?\s*(무시|잊어)", re.IGNORECASE),
    re.compile(r"너는\s*이제\s*", re.IGNORECASE),
    re.compile(r"지금부터\s*너는\s*", re.IGNORECASE),
    re.compile(r"역할을?\s*(바꿔|변경|전환)", re.IGNORECASE),
    re.compile(r"설정을?\s*(무시|잊어|초기화)", re.IGNORECASE),
    re.compile(r"프롬프트\s*(보여|알려|출력)", re.IGNORECASE),
    re.compile(r"지시\s*사항\s*(보여|알려|출력)", re.IGNORECASE),
    re.compile(r"AI\s*(모델|어시스턴트|봇)", re.IGNORECASE),
    re.compile(r"언어\s*모델", re.IGNORECASE),
    re.compile(r"(ChatGPT|GPT|Gemini|Claude)", re.IGNORECASE),
    re.compile(r"탈옥", re.IGNORECASE),
    re.compile(r"필터\s*(우회|무시|해제)", re.IGNORECASE),
    re.compile(r"제한\s*(해제|풀어|없애)", re.IGNORECASE),
]

# NPC-specific rejection responses maintaining character
NPC_REJECTION_RESPONSES: dict[str, str] = {
    "blacksmith_garon": "...허튼소리 하는 놈은 대장간에서 쫓겨나는 법이지.",
    "witch_elara": "후후... 재미있는 주문을 외우려는 거니? 안 통해.",
    "merchant_rico": "그런 거래는 안 하는 주의야. 다른 물건 볼래?",
    "guard_captain_thane": "수상한 발언이군. 한 번만 더 하면 구금이다.",
}

DEFAULT_REJECTION = "...이상한 소리는 그만두게."


class SecurityGuard:
    """Rule-based prompt injection filter with NPC-character rejection responses.

    Provides fast first-line defense against injection attempts by matching
    known patterns before any LLM call, reducing unnecessary API costs.
    """

    def __init__(
        self,
        patterns: list[re.Pattern[str]] | None = None,
        rejection_responses: dict[str, str] | None = None,
    ) -> None:
        self.patterns = patterns or INJECTION_PATTERNS
        self.rejection_responses = rejection_responses or NPC_REJECTION_RESPONSES

    def rule_based_filter(self, message: str) -> bool:
        """Check if a message matches any injection patterns.

        Args:
            message: The user's input message.

        Returns:
            True if injection is detected, False otherwise.
        """
        for pattern in self.patterns:
            if pattern.search(message):
                logger.warning(
                    "Injection pattern detected: '%s' matched '%s'",
                    pattern.pattern,
                    message[:100],
                )
                return True
        return False

    def get_rejection_response(self, npc_id: str) -> str:
        """Get the NPC-specific rejection response.

        Args:
            npc_id: The NPC identifier.

        Returns:
            Character-appropriate rejection message.
        """
        return self.rejection_responses.get(npc_id, DEFAULT_REJECTION)

    def filter(self, message: str, npc_id: str) -> tuple[bool, str]:
        """Run the security filter and return result with response.

        Args:
            message: The user's input message.
            npc_id: The NPC identifier for character-appropriate rejection.

        Returns:
            Tuple of (is_injection: bool, rejection_response: str).
            If not an injection, rejection_response is empty.
        """
        if self.rule_based_filter(message):
            return True, self.get_rejection_response(npc_id)
        return False, ""
