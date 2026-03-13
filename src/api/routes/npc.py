"""NPC REST API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from src.api.schemas import NPCProfile
from src.npc.affinity import AffinityManager, BEHAVIOR_MODIFIERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/npcs", tags=["npcs"])


@router.get("", response_model=list[NPCProfile])
async def list_npcs() -> list[dict[str, Any]]:
    """List all loaded NPCs with their current state.

    Returns basic profile information for every NPC currently loaded
    in the persona registry.
    """
    from src.api.main import get_persona_registry

    personas = get_persona_registry()
    results: list[dict[str, Any]] = []

    for npc_id, persona in personas.items():
        results.append({
            "npc_id": persona.npc_id,
            "name": persona.name,
            "occupation": persona.occupation,
            "location": persona.location,
            "personality_summary": persona.personality[:200] if persona.personality else "",
            "current_emotion": persona.current_emotion,
            "affinity": 15,  # Default; actual per-user affinity requires user context
            "affinity_level": "낯선 사람",
            "unlocked_features": [],
        })

    return results


@router.get("/{npc_id}/profile", response_model=NPCProfile)
async def get_npc_profile(npc_id: str) -> dict[str, Any]:
    """Get detailed NPC profile including affinity and unlocked content.

    Args:
        npc_id: The NPC identifier (e.g., ``blacksmith_garon``).

    Returns:
        Full NPC profile with personality, emotion, affinity, and
        list of features unlocked at the current affinity level.
    """
    from src.api.main import get_persona_registry

    personas = get_persona_registry()
    persona = personas.get(npc_id)

    if persona is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"NPC '{npc_id}' not found.")

    # Determine unlocked features at default affinity
    affinity_mgr = AffinityManager()
    modifiers = affinity_mgr.get_behavior_modifiers()
    unlocked = [
        feature
        for feature, value in modifiers.items()
        if value is True
    ]

    return {
        "npc_id": persona.npc_id,
        "name": persona.name,
        "occupation": persona.occupation,
        "location": persona.location,
        "personality_summary": persona.personality,
        "current_emotion": persona.current_emotion,
        "affinity": affinity_mgr.value,
        "affinity_level": affinity_mgr.get_level(),
        "unlocked_features": unlocked,
    }
