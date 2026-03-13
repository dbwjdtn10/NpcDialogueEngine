"""Quest progress tracker."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class QuestStatus(str, Enum):
    """Quest progression states."""

    NOT_STARTED = "not_started"
    ACTIVE = "active"
    COMPLETED = "completed"


class QuestTracker:
    """Tracks quest progress for a player.

    Manages quest states, progress percentages, and determines
    appropriate hint levels based on current progress.
    """

    def __init__(self) -> None:
        # quest_id -> (status, progress 0-100)
        self._quests: dict[str, tuple[QuestStatus, int]] = {}

    def start_quest(self, quest_id: str) -> None:
        """Mark a quest as active with 0% progress."""
        self._quests[quest_id] = (QuestStatus.ACTIVE, 0)
        logger.info("Quest started: %s", quest_id)

    def update_progress(self, quest_id: str, progress: int) -> None:
        """Update the progress of an active quest.

        Args:
            quest_id: Quest identifier.
            progress: Progress percentage (0-100).
        """
        progress = max(0, min(100, progress))
        current = self._quests.get(quest_id)

        if current is None:
            self._quests[quest_id] = (QuestStatus.ACTIVE, progress)
        else:
            status = current[0]
            if status == QuestStatus.COMPLETED:
                return  # Don't modify completed quests
            self._quests[quest_id] = (QuestStatus.ACTIVE, progress)

        if progress >= 100:
            self.complete_quest(quest_id)

    def complete_quest(self, quest_id: str) -> None:
        """Mark a quest as completed."""
        self._quests[quest_id] = (QuestStatus.COMPLETED, 100)
        logger.info("Quest completed: %s", quest_id)

    def get_status(self, quest_id: str) -> QuestStatus:
        """Get the current status of a quest."""
        entry = self._quests.get(quest_id)
        if entry is None:
            return QuestStatus.NOT_STARTED
        return entry[0]

    def get_progress(self, quest_id: str) -> int:
        """Get the progress percentage (0-100) of a quest."""
        entry = self._quests.get(quest_id)
        if entry is None:
            return 0
        return entry[1]

    def get_hint_level(self, quest_id: str) -> str:
        """Determine the appropriate hint level based on quest progress.

        Progress mapping:
        - 0% (not started): ambient (subtle environmental hints only)
        - 1-25% (just started): low (general direction)
        - 26-50% (mid progress): medium (specific location/method hints)
        - 51-75% (advanced): high (detailed guidance)
        - 76-100% (near completion): full (confirmation and next steps)

        Returns:
            Hint level string: "none", "ambient", "low", "medium", "high", "full"
        """
        progress = self.get_progress(quest_id)
        status = self.get_status(quest_id)

        if status == QuestStatus.COMPLETED:
            return "full"
        elif status == QuestStatus.NOT_STARTED:
            return "ambient"
        elif progress <= 25:
            return "low"
        elif progress <= 50:
            return "medium"
        elif progress <= 75:
            return "high"
        else:
            return "full"

    def get_active_quests(self) -> list[str]:
        """Return list of all active quest IDs."""
        return [
            quest_id
            for quest_id, (status, _) in self._quests.items()
            if status == QuestStatus.ACTIVE
        ]

    def get_all_quests(self) -> dict[str, tuple[str, int]]:
        """Return all quests with their status and progress.

        Returns:
            Dict mapping quest_id to (status_string, progress).
        """
        return {
            quest_id: (status.value, progress)
            for quest_id, (status, progress) in self._quests.items()
        }
