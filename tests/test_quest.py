"""Tests for quest system: QuestTracker, hint engine, and spoiler prevention."""

from __future__ import annotations

import pytest

from src.quest.tracker import QuestTracker, QuestStatus
from src.rag.chunker import QuestChunker


# ===========================================================================
# QuestTracker tests
# ===========================================================================

class TestQuestTracker:
    """Tests for QuestTracker status transitions."""

    @pytest.fixture
    def tracker(self) -> QuestTracker:
        return QuestTracker()

    def test_initial_status_is_not_started(self, tracker: QuestTracker):
        assert tracker.get_status("any_quest") == QuestStatus.NOT_STARTED

    def test_start_quest(self, tracker: QuestTracker):
        tracker.start_quest("main_quest_01")
        assert tracker.get_status("main_quest_01") == QuestStatus.ACTIVE
        assert tracker.get_progress("main_quest_01") == 0

    def test_update_progress(self, tracker: QuestTracker):
        tracker.start_quest("main_quest_01")
        tracker.update_progress("main_quest_01", 50)
        assert tracker.get_progress("main_quest_01") == 50
        assert tracker.get_status("main_quest_01") == QuestStatus.ACTIVE

    def test_complete_quest(self, tracker: QuestTracker):
        tracker.start_quest("main_quest_01")
        tracker.complete_quest("main_quest_01")
        assert tracker.get_status("main_quest_01") == QuestStatus.COMPLETED
        assert tracker.get_progress("main_quest_01") == 100

    def test_auto_complete_at_100_percent(self, tracker: QuestTracker):
        tracker.start_quest("main_quest_01")
        tracker.update_progress("main_quest_01", 100)
        assert tracker.get_status("main_quest_01") == QuestStatus.COMPLETED

    def test_cannot_update_completed_quest(self, tracker: QuestTracker):
        tracker.start_quest("main_quest_01")
        tracker.complete_quest("main_quest_01")
        tracker.update_progress("main_quest_01", 50)
        # Should remain completed
        assert tracker.get_status("main_quest_01") == QuestStatus.COMPLETED
        assert tracker.get_progress("main_quest_01") == 100

    def test_progress_clamped_to_bounds(self, tracker: QuestTracker):
        tracker.start_quest("main_quest_01")
        tracker.update_progress("main_quest_01", -10)
        assert tracker.get_progress("main_quest_01") == 0

        tracker.update_progress("main_quest_01", 150)
        # 150 is clamped to 100, which triggers completion
        assert tracker.get_progress("main_quest_01") == 100

    def test_get_active_quests(self, tracker: QuestTracker):
        tracker.start_quest("quest_1")
        tracker.start_quest("quest_2")
        tracker.complete_quest("quest_2")
        tracker.start_quest("quest_3")

        active = tracker.get_active_quests()
        assert "quest_1" in active
        assert "quest_2" not in active
        assert "quest_3" in active

    def test_get_all_quests(self, tracker: QuestTracker):
        tracker.start_quest("quest_1")
        tracker.update_progress("quest_1", 30)
        tracker.complete_quest("quest_1")
        tracker.start_quest("quest_2")

        all_quests = tracker.get_all_quests()
        assert all_quests["quest_1"] == ("completed", 100)
        assert all_quests["quest_2"] == ("active", 0)

    def test_update_nonexistent_quest_starts_it(self, tracker: QuestTracker):
        tracker.update_progress("new_quest", 25)
        assert tracker.get_status("new_quest") == QuestStatus.ACTIVE
        assert tracker.get_progress("new_quest") == 25

    # --- Status transition sequence ---

    def test_full_lifecycle(self, tracker: QuestTracker):
        quest_id = "main_quest_01"

        # Not started
        assert tracker.get_status(quest_id) == QuestStatus.NOT_STARTED

        # Start
        tracker.start_quest(quest_id)
        assert tracker.get_status(quest_id) == QuestStatus.ACTIVE

        # Progress through stages
        tracker.update_progress(quest_id, 25)
        assert tracker.get_progress(quest_id) == 25

        tracker.update_progress(quest_id, 75)
        assert tracker.get_progress(quest_id) == 75

        # Complete
        tracker.complete_quest(quest_id)
        assert tracker.get_status(quest_id) == QuestStatus.COMPLETED


# ===========================================================================
# HintEngine tests (built into QuestTracker)
# ===========================================================================

class TestHintEngine:
    """Tests for hint level determination based on progress."""

    @pytest.fixture
    def tracker(self) -> QuestTracker:
        return QuestTracker()

    def test_not_started_gives_ambient(self, tracker: QuestTracker):
        assert tracker.get_hint_level("unknown_quest") == "ambient"

    @pytest.mark.parametrize(
        "progress,expected_hint",
        [
            (0, "low"),  # ACTIVE with 0% progress -> low (ambient is only for NOT_STARTED)
            (1, "low"),
            (25, "low"),
            (26, "medium"),
            (50, "medium"),
            (51, "high"),
            (75, "high"),
            (76, "full"),
            (99, "full"),
        ],
    )
    def test_hint_level_for_progress(
        self, tracker: QuestTracker, progress: int, expected_hint: str
    ):
        tracker.start_quest("test_quest")
        if progress > 0:
            tracker.update_progress("test_quest", progress)
        hint = tracker.get_hint_level("test_quest")
        assert hint == expected_hint

    def test_completed_quest_gives_full(self, tracker: QuestTracker):
        tracker.start_quest("test_quest")
        tracker.complete_quest("test_quest")
        assert tracker.get_hint_level("test_quest") == "full"


# ===========================================================================
# TriggerDetector tests (keyword detection via QuestChunker)
# ===========================================================================

class TestTriggerDetector:
    """Tests for quest trigger keyword detection in chunked quest documents."""

    @pytest.fixture
    def quest_text(self) -> str:
        return """# 전설의 검 재련

## 1단계: 소문을 듣다
리코와 대화하여 드래곤 오어에 대한 소문을 듣는다.
키워드: 드래곤 오어, 전설, 드래곤릿지

## 2단계: 드래곤 오어 채취
드래곤릿지 산맥에서 드래곤 오어 3개를 채취한다.

## 3단계: 가론에게 전달
드래곤 오어를 가론에게 전달한다.
"""

    def test_keyword_in_stage_chunk(self, quest_text: str):
        """Quest-related keywords should appear in the correct stage chunk."""
        chunker = QuestChunker()
        chunks = chunker.chunk(quest_text, {"doc_type": "quest", "doc_id": "main_quest_01"})

        stage_1_chunks = [c for c in chunks if c.metadata.get("quest_stage") == 1]
        assert any("드래곤 오어" in c.content for c in stage_1_chunks)

    def test_stage_metadata_assigned(self, quest_text: str):
        chunker = QuestChunker()
        chunks = chunker.chunk(quest_text, {"doc_type": "quest", "doc_id": "main_quest_01"})

        for chunk in chunks:
            assert "quest_stage" in chunk.metadata


# ===========================================================================
# Spoiler prevention tests
# ===========================================================================

class TestSpoilerPrevention:
    """Tests that future quest stages cannot be accessed based on current progress."""

    @pytest.fixture
    def quest_chunks(self) -> list:
        """Create chunked quest with stages 0-4."""
        chunker = QuestChunker()
        text = """# 테스트 퀘스트

## 1단계: 시작
첫 번째 단계 내용

## 2단계: 중반
두 번째 단계 내용. 비밀 장소 위치.

## 3단계: 후반
세 번째 단계 내용. 최종 보스 정보.

## 4단계: 완료
네 번째 단계 내용. 엔딩 스포일러.
"""
        return chunker.chunk(text, {"doc_type": "quest", "doc_id": "test_quest"})

    def test_filter_future_stages(self, quest_chunks: list):
        """Only chunks at or before current stage should be accessible."""
        current_stage = 2

        accessible = [
            c for c in quest_chunks
            if c.metadata.get("quest_stage", 0) <= current_stage
        ]
        inaccessible = [
            c for c in quest_chunks
            if c.metadata.get("quest_stage", 0) > current_stage
        ]

        # Should have intro + stage 1 + stage 2
        assert len(accessible) >= 2
        # Should block stages 3 and 4
        assert len(inaccessible) >= 2

        # Verify no spoiler content is accessible
        accessible_text = " ".join(c.content for c in accessible)
        assert "최종 보스 정보" not in accessible_text
        assert "엔딩 스포일러" not in accessible_text

    def test_not_started_only_sees_overview(self, quest_chunks: list):
        """Before starting, only the overview/intro should be visible."""
        current_stage = 0

        accessible = [
            c for c in quest_chunks
            if c.metadata.get("quest_stage", 0) <= current_stage
        ]

        # Only the intro chunk (before first ## header)
        for chunk in accessible:
            assert chunk.metadata.get("quest_stage", 0) == 0

    def test_completed_sees_everything(self, quest_chunks: list):
        """After completion, all stages should be visible."""
        max_stage = max(c.metadata.get("quest_stage", 0) for c in quest_chunks)

        accessible = [
            c for c in quest_chunks
            if c.metadata.get("quest_stage", 0) <= max_stage
        ]
        assert len(accessible) == len(quest_chunks)
