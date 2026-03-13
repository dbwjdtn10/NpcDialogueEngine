"""Affinity (favorability) system for NPC-player relationships."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Affinity level thresholds and names
AFFINITY_LEVELS: list[tuple[int, int, str]] = [
    (0, 20, "낯선 사람"),
    (21, 40, "아는 사이"),
    (41, 60, "친구"),
    (61, 80, "절친"),
    (81, 100, "맹우"),
]

# Behavior modifiers unlocked at each affinity level
BEHAVIOR_MODIFIERS: dict[str, dict[str, bool | str]] = {
    "낯선 사람": {
        "basic_greeting": True,
        "quest_hints": False,
        "lore_secrets": False,
        "discounts": False,
        "hidden_quests": False,
        "special_items": False,
        "companion": False,
        "info_depth": "minimal",
    },
    "아는 사이": {
        "basic_greeting": True,
        "quest_hints": True,
        "lore_secrets": False,
        "discounts": False,
        "hidden_quests": False,
        "special_items": False,
        "companion": False,
        "info_depth": "basic",
    },
    "친구": {
        "basic_greeting": True,
        "quest_hints": True,
        "lore_secrets": True,
        "discounts": True,
        "hidden_quests": False,
        "special_items": False,
        "companion": False,
        "info_depth": "detailed",
    },
    "절친": {
        "basic_greeting": True,
        "quest_hints": True,
        "lore_secrets": True,
        "discounts": True,
        "hidden_quests": True,
        "special_items": True,
        "companion": False,
        "info_depth": "full",
    },
    "맹우": {
        "basic_greeting": True,
        "quest_hints": True,
        "lore_secrets": True,
        "discounts": True,
        "hidden_quests": True,
        "special_items": True,
        "companion": True,
        "info_depth": "full",
    },
}


class AffinityManager:
    """Manages the affinity score between a player and an NPC.

    Affinity ranges from 0 to 100, with an initial value of 15 (stranger).
    Different affinity levels unlock different NPC behaviors and content.
    """

    INITIAL_AFFINITY: int = 15
    MIN_AFFINITY: int = 0
    MAX_AFFINITY: int = 100

    def __init__(self, initial_value: int = INITIAL_AFFINITY) -> None:
        self._affinity: int = max(
            self.MIN_AFFINITY, min(self.MAX_AFFINITY, initial_value)
        )

    @property
    def value(self) -> int:
        """Current affinity score."""
        return self._affinity

    def get_level(self) -> str:
        """Get the current affinity level name.

        Returns:
            Korean level name: 낯선 사람, 아는 사이, 친구, 절친, or 맹우.
        """
        for low, high, name in AFFINITY_LEVELS:
            if low <= self._affinity <= high:
                return name
        return "맹우"  # Fallback for edge cases

    def update(self, delta: int) -> int:
        """Update affinity by delta amount with bounds checking.

        Args:
            delta: Amount to change affinity (positive or negative).

        Returns:
            The new affinity value after update.
        """
        old_value = self._affinity
        self._affinity = max(
            self.MIN_AFFINITY,
            min(self.MAX_AFFINITY, self._affinity + delta),
        )

        if old_value != self._affinity:
            logger.debug(
                "Affinity updated: %d -> %d (delta=%+d, level=%s)",
                old_value,
                self._affinity,
                delta,
                self.get_level(),
            )

        return self._affinity

    def get_behavior_modifiers(self) -> dict[str, bool | str]:
        """Get the behavior modifiers unlocked at the current affinity level.

        Returns:
            Dictionary of behavior flags and their values.
        """
        level = self.get_level()
        return BEHAVIOR_MODIFIERS.get(level, BEHAVIOR_MODIFIERS["낯선 사람"]).copy()
