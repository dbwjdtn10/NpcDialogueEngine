"""Shared pytest fixtures for NPC Dialogue Engine tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Sample NPC persona
# ---------------------------------------------------------------------------

SAMPLE_NPC_PERSONA = """# 대장장이 가론 (Garon the Blacksmith)

## 기본 정보
- 나이: 52세
- 종족: 인간
- 직업: 대장장이 (마스터 등급)
- 위치: 아이언포지 마을 중앙 대장간

## 성격
- 과묵하지만 진심이 담긴 말을 함
- 장인 정신이 강하고, 대충 만든 무기를 경멸
- 젊은 모험가에게 은근히 호의적

## 말투
- 짧고 직설적인 문장 선호
- "...흠" 같은 감탄사를 자주 씀
- 무기/방어구 관련 전문 용어 사용
- 존댓말 안 씀

## 지식 범위
- 무기/방어구 제작
- 광석/금속 종류
- 아이언포지 마을 역사
- 전쟁 경험
"""

SAMPLE_NPC_PERSONA_ELARA = """# 마녀 엘라라 (Witch Elara)

## 기본 정보
- 나이: 외형 30대 (실제 나이 불명)
- 종족: 반엘프
- 직업: 마녀/연금술사
- 위치: 아이언포지 외곽 마녀의 오두막

## 성격
- 장난기 많고 신비로운 분위기
- 지식욕이 강함

## 말투
- "후후" 같은 웃음을 자주 씀
- 존댓말과 반말 혼용
- 비유적 표현 선호
"""


@pytest.fixture
def sample_npc_persona() -> str:
    """Return a sample NPC persona markdown string."""
    return SAMPLE_NPC_PERSONA


@pytest.fixture
def sample_npc_persona_elara() -> str:
    """Return Elara NPC persona markdown string."""
    return SAMPLE_NPC_PERSONA_ELARA


# ---------------------------------------------------------------------------
# Sample quest data
# ---------------------------------------------------------------------------

SAMPLE_QUEST_DATA = {
    "quest_id": "main_quest_01",
    "title": "전설의 검 재련",
    "stages": [
        {"stage": 1, "name": "소문을 듣다", "description": "리코와 대화"},
        {"stage": 2, "name": "드래곤 오어 채취", "description": "드래곤릿지에서 광석 수집"},
        {"stage": 3, "name": "가론에게 전달", "description": "드래곤 오어 전달"},
        {"stage": 4, "name": "전설의 검 수령", "description": "완성된 검 수령"},
    ],
    "related_npcs": ["blacksmith_garon", "merchant_rico", "guard_captain_thane", "witch_elara"],
}


@pytest.fixture
def sample_quest_data() -> dict:
    """Return sample quest data."""
    return SAMPLE_QUEST_DATA


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    """Return a mock LLM that returns configurable responses."""
    llm = MagicMock()

    def make_response(content: str):
        resp = MagicMock()
        resp.content = content
        return resp

    llm.invoke = MagicMock(
        return_value=make_response('{"intent": "general_chat", "intent_confidence": 0.9, '
                                   '"sentiment": "neutral", "sentiment_intensity": 0.3, '
                                   '"security": "normal", "is_repeated_question": false}')
    )
    llm.make_response = make_response
    return llm


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Return a mock Redis client."""
    redis_client = AsyncMock()
    redis_client.get = AsyncMock(return_value=None)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=True)
    redis_client.exists = AsyncMock(return_value=False)
    redis_client.expire = AsyncMock(return_value=True)
    redis_client.ping = AsyncMock(return_value=True)
    return redis_client


# ---------------------------------------------------------------------------
# Mock ChromaDB
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_chroma_collection():
    """Return a mock ChromaDB collection."""
    collection = MagicMock()
    collection.name = "worldbuilding"

    collection.query = MagicMock(return_value={
        "ids": [["doc_1", "doc_2", "doc_3"]],
        "documents": [[
            "가론은 아이언포지 마을의 대장장이다.",
            "드래곤 오어는 전설의 재료이다.",
            "아이언포지 마을은 교역의 중심지이다.",
        ]],
        "metadatas": [[
            {"doc_type": "npc", "doc_id": "blacksmith_garon", "section": "기본 정보"},
            {"doc_type": "lore", "doc_id": "history", "section": "개요"},
            {"doc_type": "lore", "doc_id": "geography", "section": "아이언포지"},
        ]],
        "distances": [[0.1, 0.2, 0.3]],
    })

    collection.get = MagicMock(return_value={
        "ids": ["doc_1", "doc_2", "doc_3"],
        "documents": [
            "가론은 아이언포지 마을의 대장장이다.",
            "드래곤 오어는 전설의 재료이다.",
            "아이언포지 마을은 교역의 중심지이다.",
        ],
        "metadatas": [
            {"doc_type": "npc", "doc_id": "blacksmith_garon", "section": "기본 정보"},
            {"doc_type": "lore", "doc_id": "history", "section": "개요"},
            {"doc_type": "lore", "doc_id": "geography", "section": "아이언포지"},
        ],
    })

    collection.add = MagicMock()
    collection.count = MagicMock(return_value=3)

    return collection


# ---------------------------------------------------------------------------
# Sample RAG sources
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_rag_sources() -> list[str]:
    """Return sample RAG source chunks."""
    return [
        "가론은 아이언포지 마을의 대장장이로, 52세 인간 남성이다. 드워프 장로 토린에게 단조 기술을 배웠다.",
        "드래곤 오어는 드래곤의 화염으로 변형된 특수 광석으로, 드래곤릿지 산맥에서 발견된다.",
        "아이언포지 마을은 드워프 동맹 이후 교역의 중심지로 성장했다.",
    ]


# ---------------------------------------------------------------------------
# Sample worldbuilding entities
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_known_entities() -> set[str]:
    """Return a set of known worldbuilding entity names."""
    return {
        "가론", "엘라라", "리코", "테인", "토린",
        "아이언포지", "드래곤릿지", "크라운시티", "실버레이크",
        "드래곤 오어", "드래곤슬레이어", "미스릴", "아다만타이트",
        "어둠의 결사", "왕국 수호대", "은빛나무 일족",
        "이그니스", "아쿠아", "테라", "벤투스",
        "벨로크", "실바리온", "에릭", "칼렌 아스테리우스",
        "아스테리아", "Garon", "Elara", "Rico", "Thane",
        "Iron Longsword", "Wind Dagger", "Reinforced Steel Greatsword",
        "blacksmith_garon", "witch_elara", "merchant_rico", "guard_captain_thane",
    }
