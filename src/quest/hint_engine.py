"""Quest hint engine with spoiler prevention based on player progress."""

from __future__ import annotations

import logging
from typing import Optional

from src.rag.retriever import HybridRetriever, RetrievalResult
from src.quest.tracker import QuestTracker

logger = logging.getLogger(__name__)

# Hint level to max accessible quest stage mapping
HINT_LEVEL_MAX_STAGE: dict[str, int] = {
    "none": 0,
    "ambient": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "full": 999,  # No limit
}


class HintEngine:
    """Provides quest hints appropriate to the player's progress level.

    Prevents spoilers by restricting access to quest chunks based on
    the current quest stage. Only current and previous stage information
    is accessible.
    """

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        quest_tracker: Optional[QuestTracker] = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.quest_tracker = quest_tracker or QuestTracker()

    def get_hint_context(
        self,
        query: str,
        quest_id: str,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        """Retrieve quest-related context filtered by progress stage.

        Only returns chunks from stages the player has already reached
        or is currently on, preventing spoilers for future content.

        Args:
            query: The user's query about the quest.
            quest_id: The quest identifier.
            top_k: Maximum number of results to return.

        Returns:
            List of RetrievalResult filtered by accessible quest stages.
        """
        hint_level = self.quest_tracker.get_hint_level(quest_id)
        max_stage = HINT_LEVEL_MAX_STAGE.get(hint_level, 0)

        if max_stage == 0:
            logger.debug(
                "Quest %s hint_level=%s: no hints available",
                quest_id,
                hint_level,
            )
            return []

        # Retrieve quest documents
        results = self.retriever.retrieve(
            query=query,
            doc_type_filter="quest",
            top_k=top_k * 3,  # Fetch extra to compensate for filtering
        )

        # Filter by quest_id and accessible stage
        filtered: list[RetrievalResult] = []
        for result in results:
            doc_id = result.metadata.get("doc_id", "")
            quest_stage = result.metadata.get("quest_stage", 0)

            # Only include chunks from the target quest
            if quest_id not in str(doc_id):
                continue

            # Ensure quest_stage is an int
            try:
                stage_num = int(quest_stage)
            except (ValueError, TypeError):
                stage_num = 0

            # Only allow access to current and previous stages
            if stage_num <= max_stage:
                filtered.append(result)

        # Limit to top_k
        filtered = filtered[:top_k]

        logger.debug(
            "Quest %s: hint_level=%s, max_stage=%d, returned %d chunks",
            quest_id,
            hint_level,
            max_stage,
            len(filtered),
        )

        return filtered

    def get_hint_summary(self, quest_id: str) -> str:
        """Get a summary of the player's current hint access for a quest.

        Args:
            quest_id: The quest identifier.

        Returns:
            Human-readable hint level description.
        """
        hint_level = self.quest_tracker.get_hint_level(quest_id)
        progress = self.quest_tracker.get_progress(quest_id)

        descriptions = {
            "none": "힌트 제공 불가 (퀘스트 미발견)",
            "ambient": "간접적 힌트만 가능 (분위기 조성)",
            "low": "기본 방향 힌트 가능 (일반적 위치/방법)",
            "medium": "구체적 힌트 가능 (세부 장소/도구)",
            "high": "상세 힌트 가능 (직접적 안내)",
            "full": "모든 정보 제공 가능",
        }

        return f"진행도: {progress}% | 힌트 수준: {descriptions.get(hint_level, '알 수 없음')}"
