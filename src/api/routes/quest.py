"""Quest REST API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query

from src.api.schemas import PaginatedResponse, QuestStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/quests", tags=["quests"])

# In-memory quest metadata store (would come from DB / worldbuilding docs in production)
_QUEST_METADATA: dict[str, dict[str, Any]] = {
    "main_quest_01": {
        "title": "전설의 검",
        "related_npcs": ["blacksmith_garon"],
    },
    "main_quest_02": {
        "title": "마녀의 부탁",
        "related_npcs": ["witch_elara", "blacksmith_garon"],
    },
    "side_quest_01": {
        "title": "희귀 광석 수집",
        "related_npcs": ["blacksmith_garon"],
    },
}


def _get_quest_tracker():
    """Lazy import to avoid circular dependency."""
    from src.api.main import get_quest_tracker
    return get_quest_tracker()


@router.get("", response_model=PaginatedResponse[QuestStatus])
async def list_quests(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max items to return"),
    status_filter: str | None = Query(None, description="Filter by status: not_started, active, completed"),
) -> dict[str, Any]:
    """List all quests with their current progress (paginated).

    Returns every known quest (both from metadata and any the player
    has interacted with) along with status and progress percentage.
    Supports offset-based pagination and optional status filtering.
    """
    tracker = _get_quest_tracker()
    all_quests = tracker.get_all_quests()

    results: list[dict[str, Any]] = []

    # Include quests from metadata
    seen_ids: set[str] = set()
    for quest_id, meta in _QUEST_METADATA.items():
        seen_ids.add(quest_id)
        status_str, progress = all_quests.get(quest_id, ("not_started", 0))
        results.append({
            "quest_id": quest_id,
            "title": meta.get("title", ""),
            "status": status_str,
            "progress": progress,
            "current_stage": None,
            "related_npcs": meta.get("related_npcs", []),
        })

    # Include any additional quests the tracker knows about
    for quest_id, (status_str, progress) in all_quests.items():
        if quest_id in seen_ids:
            continue
        results.append({
            "quest_id": quest_id,
            "title": "",
            "status": status_str,
            "progress": progress,
            "current_stage": None,
            "related_npcs": [],
        })

    # Apply status filter
    if status_filter:
        results = [q for q in results if q["status"] == status_filter]

    total = len(results)
    paginated = results[skip : skip + limit]

    return {
        "items": paginated,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + limit) < total,
    }


@router.get("/{quest_id}", response_model=QuestStatus)
async def get_quest_detail(quest_id: str) -> dict[str, Any]:
    """Get detailed quest information including progress.

    Args:
        quest_id: The quest identifier (e.g., ``main_quest_01``).

    Returns:
        Quest status, progress, related NPCs, and metadata.
    """
    tracker = _get_quest_tracker()
    meta = _QUEST_METADATA.get(quest_id, {})

    status = tracker.get_status(quest_id)
    progress = tracker.get_progress(quest_id)

    if not meta and status.value == "not_started":
        from src.api.exceptions import APIError, ErrorCode
        raise APIError(
            code=ErrorCode.QUEST_NOT_FOUND,
            message=f"Quest '{quest_id}' not found.",
            status_code=404,
        )

    return {
        "quest_id": quest_id,
        "title": meta.get("title", ""),
        "status": status.value,
        "progress": progress,
        "current_stage": None,
        "related_npcs": meta.get("related_npcs", []),
    }
