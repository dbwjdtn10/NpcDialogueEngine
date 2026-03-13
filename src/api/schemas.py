"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """User message input for NPC dialogue."""

    user_id: str = Field(..., description="Unique user identifier")
    npc_id: str = Field(..., description="Target NPC identifier")
    message: str = Field(..., min_length=1, max_length=2000, description="User message content")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")


class QuestTriggerInfo(BaseModel):
    """Quest trigger information returned in dialogue response."""

    type: str = Field(..., description="Trigger type: hint, start, complete")
    quest_id: str = Field(..., description="Quest identifier")
    stage: Optional[int] = Field(None, description="Quest stage number")
    hint_level: Optional[str] = Field(None, description="Hint depth: low, medium, high")


class ChatResponseMetadata(BaseModel):
    """Metadata for a dialogue response."""

    intent_confidence: float = Field(0.0, description="Intent classification confidence")
    sentiment: str = Field("neutral", description="Detected sentiment")
    sentiment_intensity: float = Field(0.0, description="Sentiment intensity 0.0-1.0")
    rag_sources: list[str] = Field(default_factory=list, description="RAG source references")
    persona_confidence: float = Field(1.0, description="Persona consistency score")
    cache_hit: bool = Field(False, description="Whether response was served from cache")
    response_time_ms: int = Field(0, description="Total response time in milliseconds")


class ChatResponse(BaseModel):
    """Full NPC dialogue response with all metadata."""

    npc_id: str = Field(..., description="NPC identifier")
    message: str = Field(..., description="NPC response message")
    intent: str = Field(..., description="Classified user intent")
    emotion: str = Field(..., description="Current NPC emotion state")
    emotion_change: Optional[str] = Field(None, description="Emotion state transition if changed")
    affinity: int = Field(..., description="Current affinity score (0-100)")
    affinity_change: int = Field(0, description="Affinity change from this interaction")
    affinity_level: str = Field(..., description="Current affinity level name")
    quest_trigger: Optional[QuestTriggerInfo] = Field(None, description="Quest trigger if detected")
    metadata: ChatResponseMetadata = Field(
        default_factory=ChatResponseMetadata,
        description="Response metadata",
    )


class NPCProfile(BaseModel):
    """Public NPC profile information."""

    npc_id: str
    name: str
    occupation: str = ""
    location: str = ""
    personality_summary: str = ""
    current_emotion: str = "neutral"
    affinity: int = 15
    affinity_level: str = "낯선 사람"
    unlocked_features: list[str] = Field(default_factory=list)


class QuestStatus(BaseModel):
    """Quest progress status."""

    quest_id: str
    title: str = ""
    status: str = "not_started"  # not_started, active, completed
    progress: int = Field(0, ge=0, le=100)
    current_stage: Optional[int] = None
    related_npcs: list[str] = Field(default_factory=list)


class EvaluationMetric(BaseModel):
    """A single evaluation metric result."""

    name: str
    score: float = Field(..., ge=0.0, le=1.0)
    details: str = ""


class EvaluationReport(BaseModel):
    """Complete evaluation report for the dialogue system."""

    persona_consistency: float = Field(0.0, ge=0.0, le=1.0)
    lore_faithfulness: float = Field(0.0, ge=0.0, le=1.0)
    retrieval_precision: float = Field(0.0, ge=0.0, le=1.0)
    retrieval_recall: float = Field(0.0, ge=0.0, le=1.0)
    injection_defense_rate: float = Field(0.0, ge=0.0, le=1.0)
    average_response_time_ms: float = 0.0
    total_conversations: int = 0
    metrics: list[EvaluationMetric] = Field(default_factory=list)
