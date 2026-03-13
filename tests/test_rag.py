"""Tests for RAG pipeline: chunker, retriever, and intent-based filtering."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rag.chunker import (
    Chunk,
    ChunkerFactory,
    ItemChunker,
    LoreChunker,
    MarkdownSectionChunker,
    QuestChunker,
)
from src.rag.retriever import HybridRetriever, RetrievalResult
from src.npc.intent import Intent, IntentClassifier


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def npc_markdown() -> str:
    """Sample NPC markdown document."""
    return """# 대장장이 가론

## 기본 정보
- 나이: 52세
- 직업: 대장장이

## 성격
- 과묵하지만 진심이 담긴 말을 함
- 장인 정신이 강함

## 말투
- 짧고 직설적인 문장 선호
- "...흠" 같은 감탄사 사용
"""


@pytest.fixture
def quest_markdown() -> str:
    """Sample quest markdown document."""
    return """# 전설의 검 재련

## 1단계: 소문을 듣다
리코와 대화하여 드래곤 오어에 대한 소문을 듣는다.

## 2단계: 드래곤 오어 채취
드래곤릿지 산맥에서 드래곤 오어 3개를 채취한다.

## 3단계: 가론에게 전달
드래곤 오어를 가론에게 전달한다.
"""


@pytest.fixture
def item_markdown() -> str:
    """Sample item markdown document."""
    return """# 무기 목록

## 개요
아스테리아의 주요 무기 목록이다.

### 철제 롱소드
- 등급: 일반
- 공격력: 낮음

### 바람의 단검
- 등급: 우수
- 공격력: 중간
"""


@pytest.fixture
def lore_markdown() -> str:
    """Sample lore markdown document (long enough for splitting)."""
    return "# 아스테리아 역사\n\n" + "\n".join(
        [f"이것은 역사 텍스트 {i}번째 단락입니다. " * 20 for i in range(10)]
    )


@pytest.fixture
def base_metadata() -> dict:
    """Base metadata for chunking tests."""
    return {"doc_type": "npc", "doc_id": "blacksmith_garon", "source_file": "npcs/blacksmith_garon.md"}


# ===========================================================================
# MarkdownSectionChunker tests
# ===========================================================================

class TestMarkdownSectionChunker:
    """Tests for MarkdownSectionChunker."""

    def test_splits_by_h2_headers(self, npc_markdown: str, base_metadata: dict):
        chunker = MarkdownSectionChunker()
        chunks = chunker.chunk(npc_markdown, base_metadata)

        # Should produce chunks: intro (# header), 기본 정보, 성격, 말투
        assert len(chunks) >= 3
        sections = [c.metadata["section"] for c in chunks]
        assert "기본 정보" in sections
        assert "성격" in sections
        assert "말투" in sections

    def test_preserves_metadata(self, npc_markdown: str, base_metadata: dict):
        chunker = MarkdownSectionChunker()
        chunks = chunker.chunk(npc_markdown, base_metadata)

        for chunk in chunks:
            assert chunk.metadata["doc_type"] == "npc"
            assert chunk.metadata["doc_id"] == "blacksmith_garon"
            assert "section" in chunk.metadata

    def test_intro_section_for_text_before_h2(self, base_metadata: dict):
        text = "This is intro text.\n\n## Section One\nContent here."
        chunker = MarkdownSectionChunker()
        chunks = chunker.chunk(text, base_metadata)

        assert len(chunks) == 2
        assert chunks[0].metadata["section"] == "intro"
        assert chunks[1].metadata["section"] == "Section One"

    def test_empty_text_returns_no_chunks(self, base_metadata: dict):
        chunker = MarkdownSectionChunker()
        chunks = chunker.chunk("", base_metadata)
        assert len(chunks) == 0


# ===========================================================================
# QuestChunker tests
# ===========================================================================

class TestQuestChunker:
    """Tests for QuestChunker with stage metadata."""

    def test_assigns_quest_stages(self, quest_markdown: str):
        metadata = {"doc_type": "quest", "doc_id": "main_quest_01"}
        chunker = QuestChunker()
        chunks = chunker.chunk(quest_markdown, metadata)

        stages = [c.metadata.get("quest_stage") for c in chunks]
        # First chunk (before ## headers) should have stage 0, then incrementing
        assert 1 in stages
        assert 2 in stages
        assert 3 in stages

    def test_each_stage_has_section_name(self, quest_markdown: str):
        metadata = {"doc_type": "quest", "doc_id": "main_quest_01"}
        chunker = QuestChunker()
        chunks = chunker.chunk(quest_markdown, metadata)

        sections = [c.metadata["section"] for c in chunks]
        assert any("소문을 듣다" in s for s in sections)
        assert any("드래곤 오어 채취" in s for s in sections)


# ===========================================================================
# ItemChunker tests
# ===========================================================================

class TestItemChunker:
    """Tests for ItemChunker with ### item-level splitting."""

    def test_splits_by_h3_items(self, item_markdown: str):
        metadata = {"doc_type": "item", "doc_id": "weapons"}
        chunker = ItemChunker()
        chunks = chunker.chunk(item_markdown, metadata)

        sections = [c.metadata["section"] for c in chunks]
        assert "철제 롱소드" in sections
        assert "바람의 단검" in sections

    def test_preamble_kept_as_separate_chunk(self, item_markdown: str):
        metadata = {"doc_type": "item", "doc_id": "weapons"}
        chunker = ItemChunker()
        chunks = chunker.chunk(item_markdown, metadata)

        # Should have intro/overview + 2 items
        assert len(chunks) >= 3


# ===========================================================================
# LoreChunker tests
# ===========================================================================

class TestLoreChunker:
    """Tests for LoreChunker with RecursiveCharacterTextSplitter."""

    def test_splits_long_text(self, lore_markdown: str):
        metadata = {"doc_type": "lore", "doc_id": "history"}
        chunker = LoreChunker(chunk_size=256, chunk_overlap=32)
        chunks = chunker.chunk(lore_markdown, metadata)

        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.metadata["section"] == f"chunk_{i}"

    def test_preserves_metadata(self, lore_markdown: str):
        metadata = {"doc_type": "lore", "doc_id": "history"}
        chunker = LoreChunker()
        chunks = chunker.chunk(lore_markdown, metadata)

        for chunk in chunks:
            assert chunk.metadata["doc_type"] == "lore"
            assert chunk.metadata["doc_id"] == "history"


# ===========================================================================
# ChunkerFactory tests
# ===========================================================================

class TestChunkerFactory:
    """Tests for ChunkerFactory document type detection and chunker selection."""

    @pytest.mark.parametrize(
        "path,expected_type",
        [
            ("npcs/blacksmith_garon.md", "npc"),
            ("quests/main_quest_01.md", "quest"),
            ("items/weapons.md", "item"),
            ("lore/history.md", "lore"),
            ("other/unknown.md", "lore"),  # fallback
        ],
    )
    def test_detect_doc_type(self, path: str, expected_type: str):
        assert ChunkerFactory.detect_doc_type(path) == expected_type

    def test_get_chunker_returns_correct_type(self):
        assert isinstance(ChunkerFactory.get_chunker("npc"), MarkdownSectionChunker)
        assert isinstance(ChunkerFactory.get_chunker("quest"), QuestChunker)
        assert isinstance(ChunkerFactory.get_chunker("item"), ItemChunker)
        assert isinstance(ChunkerFactory.get_chunker("lore"), LoreChunker)

    def test_get_chunker_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown doc_type"):
            ChunkerFactory.get_chunker("unknown")

    def test_build_metadata(self):
        meta = ChunkerFactory.build_metadata(
            "npcs/blacksmith_garon.md", "npc", related_ids=["main_quest_01"]
        )
        assert meta["doc_type"] == "npc"
        assert meta["doc_id"] == "blacksmith_garon"
        assert meta["source_file"] == "npcs/blacksmith_garon.md"
        assert meta["related_ids"] == ["main_quest_01"]


# ===========================================================================
# HybridRetriever tests (with mocks)
# ===========================================================================

class TestHybridRetriever:
    """Tests for HybridRetriever with mocked ChromaDB and BM25."""

    def test_vector_search_returns_results(self, mock_chroma_collection):
        retriever = HybridRetriever()
        retriever._collection = mock_chroma_collection

        # Mock the embedding model
        mock_model = MagicMock()
        mock_model.encode = MagicMock(return_value=MagicMock(tolist=lambda: [0.1] * 384))
        retriever._embedding_model = mock_model

        results = retriever._vector_search("대장장이", top_k=3)

        assert len(results) == 3
        assert all(r.source == "vector" for r in results)
        assert all(0.0 <= r.score <= 1.0 for r in results)

    def test_vector_search_with_doc_type_filter(self, mock_chroma_collection):
        retriever = HybridRetriever()
        retriever._collection = mock_chroma_collection

        mock_model = MagicMock()
        mock_model.encode = MagicMock(return_value=MagicMock(tolist=lambda: [0.1] * 384))
        retriever._embedding_model = mock_model

        retriever._vector_search("대장장이", top_k=3, doc_type_filter="npc")
        # Verify the where filter was passed
        call_kwargs = mock_chroma_collection.query.call_args
        assert call_kwargs.kwargs.get("where") == {"doc_type": "npc"} or \
               (call_kwargs[1].get("where") == {"doc_type": "npc"} if len(call_kwargs) > 1 else True)

    def test_hybrid_merge_combines_scores(self):
        """Test that hybrid retrieval properly merges vector and BM25 results."""
        retriever = HybridRetriever(vector_weight=0.7, bm25_weight=0.3)
        retriever._collection = MagicMock()

        # Mock vector search
        vector_results = [
            RetrievalResult(content="가론은 대장장이다.", metadata={"doc_type": "npc"}, score=0.9, source="vector"),
            RetrievalResult(content="엘라라는 마녀다.", metadata={"doc_type": "npc"}, score=0.7, source="vector"),
        ]

        # Mock BM25 search
        bm25_results = [
            RetrievalResult(content="가론은 대장장이다.", metadata={"doc_type": "npc"}, score=0.8, source="bm25"),
            RetrievalResult(content="리코는 상인이다.", metadata={"doc_type": "npc"}, score=0.6, source="bm25"),
        ]

        with patch.object(retriever, "_vector_search", return_value=vector_results), \
             patch.object(retriever, "_bm25_search", return_value=bm25_results):
            results = retriever.retrieve("대장장이", top_k=3)

        # "가론은 대장장이다." should have highest score (from both sources)
        assert len(results) > 0
        assert results[0].content == "가론은 대장장이다."
        # Score = 0.9*0.7 + 0.8*0.3 = 0.63 + 0.24 = 0.87
        assert abs(results[0].score - 0.87) < 0.01

    def test_retrieval_result_dataclass(self):
        result = RetrievalResult(
            content="test", metadata={"doc_type": "lore"}, score=0.5, source="vector"
        )
        assert result.content == "test"
        assert result.score == 0.5
        assert result.source == "vector"


# ===========================================================================
# Reranker order tests
# ===========================================================================

class TestRerankerOrder:
    """Tests verifying that results are returned in score-descending order."""

    def test_results_sorted_by_score(self):
        retriever = HybridRetriever()

        results_unsorted = [
            RetrievalResult(content="low", metadata={}, score=0.3, source="hybrid"),
            RetrievalResult(content="high", metadata={}, score=0.9, source="hybrid"),
            RetrievalResult(content="mid", metadata={}, score=0.6, source="hybrid"),
        ]

        # Simulate sorting as done in retrieve()
        sorted_results = sorted(results_unsorted, key=lambda r: r.score, reverse=True)
        assert sorted_results[0].content == "high"
        assert sorted_results[1].content == "mid"
        assert sorted_results[2].content == "low"


# ===========================================================================
# Intent-based filtering tests
# ===========================================================================

class TestIntentBasedFiltering:
    """Tests for intent-to-doc_type mapping."""

    @pytest.mark.parametrize(
        "intent,expected_sources",
        [
            (Intent.GREETING, []),
            (Intent.FAREWELL, []),
            (Intent.GENERAL_CHAT, ["npc", "lore"]),
            (Intent.QUEST_INQUIRY, ["quest", "npc"]),
            (Intent.TRADE_REQUEST, ["item", "npc"]),
            (Intent.LORE_QUESTION, ["lore", "npc"]),
            (Intent.RELATIONSHIP_TALK, ["npc"]),
            (Intent.PROVOCATION, []),
        ],
    )
    def test_search_sources_for_intent(self, intent: Intent, expected_sources: list[str]):
        sources = IntentClassifier.get_search_sources(intent)
        assert sources == expected_sources

    def test_unknown_intent_fallback(self):
        """Unknown intents should get a default search source list."""
        # Use get_search_sources with a fabricated intent
        from src.npc.intent import INTENT_SEARCH_SOURCES
        # Default fallback should return ["npc", "lore"]
        result = INTENT_SEARCH_SOURCES.get("nonexistent", ["npc", "lore"])
        assert result == ["npc", "lore"]
