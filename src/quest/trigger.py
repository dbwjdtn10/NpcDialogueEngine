"""Quest trigger detection from user dialogue messages."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TriggerConfig:
    """Configuration for a single quest trigger."""

    quest_id: str
    keywords: list[str]
    intents: list[str]
    npc_ids: list[str]  # Which NPCs can trigger this
    trigger_type: str  # "start", "hint", "complete"
    stage: Optional[int] = None


# Default quest triggers (can be loaded from config or quest documents)
DEFAULT_TRIGGERS: list[TriggerConfig] = [
    TriggerConfig(
        quest_id="main_quest_01",
        keywords=["전설의 검", "전설", "특별한 검", "명검"],
        intents=["quest_inquiry", "lore_question"],
        npc_ids=["blacksmith_garon"],
        trigger_type="start",
        stage=1,
    ),
    TriggerConfig(
        quest_id="main_quest_01",
        keywords=["드래곤 광석", "광석 구해", "재료 가져"],
        intents=["quest_inquiry", "trade_request"],
        npc_ids=["blacksmith_garon"],
        trigger_type="complete",
        stage=2,
    ),
    TriggerConfig(
        quest_id="side_quest_01",
        keywords=["희귀 광석", "광석 수집", "광석 찾"],
        intents=["quest_inquiry"],
        npc_ids=["blacksmith_garon"],
        trigger_type="start",
        stage=1,
    ),
    TriggerConfig(
        quest_id="main_quest_02",
        keywords=["엘라라가 보내", "마녀가 보내", "소개받"],
        intents=["quest_inquiry", "relationship_talk"],
        npc_ids=["blacksmith_garon", "witch_elara"],
        trigger_type="start",
        stage=1,
    ),
]


class TriggerDetector:
    """Detects quest triggers from user messages and intent classification.

    Checks both keyword patterns and intent classifications to determine
    if a user's dialogue should trigger a quest event.
    """

    def __init__(
        self,
        triggers: list[TriggerConfig] | None = None,
    ) -> None:
        self.triggers = triggers or DEFAULT_TRIGGERS

    def detect(
        self,
        user_message: str,
        intent: str,
        npc_id: str,
    ) -> Optional[dict[str, Any]]:
        """Detect if a user message triggers a quest event.

        Args:
            user_message: The player's input message.
            intent: Classified intent string.
            npc_id: The NPC being spoken to.

        Returns:
            Trigger info dict if a trigger is detected, None otherwise.
            Dict format: {type, quest_id, stage, hint_level}
        """
        message_lower = user_message.lower()

        for trigger in self.triggers:
            # Check if this NPC can activate this trigger
            if npc_id not in trigger.npc_ids:
                continue

            # Check if intent matches
            if intent not in trigger.intents:
                continue

            # Check for keyword matches
            keyword_match = any(
                keyword in message_lower for keyword in trigger.keywords
            )

            if keyword_match:
                logger.info(
                    "Quest trigger detected: %s (%s) for NPC %s",
                    trigger.quest_id,
                    trigger.trigger_type,
                    npc_id,
                )

                return {
                    "type": trigger.trigger_type,
                    "quest_id": trigger.quest_id,
                    "stage": trigger.stage,
                    "hint_level": self._get_hint_level_for_trigger(trigger),
                }

        return None

    @staticmethod
    def _get_hint_level_for_trigger(trigger: TriggerConfig) -> Optional[str]:
        """Determine hint level based on trigger type."""
        if trigger.trigger_type == "start":
            return "low"
        elif trigger.trigger_type == "complete":
            return None
        elif trigger.trigger_type == "hint":
            return "medium"
        return None

    def add_trigger(self, trigger: TriggerConfig) -> None:
        """Add a new quest trigger configuration."""
        self.triggers.append(trigger)

    def remove_triggers_for_quest(self, quest_id: str) -> int:
        """Remove all triggers for a given quest.

        Returns:
            Number of triggers removed.
        """
        original_count = len(self.triggers)
        self.triggers = [t for t in self.triggers if t.quest_id != quest_id]
        removed = original_count - len(self.triggers)
        if removed > 0:
            logger.info("Removed %d triggers for quest %s", removed, quest_id)
        return removed
