"""Tests for NPC systems: EmotionMachine, AffinityManager, and persona loading."""

from __future__ import annotations

import pytest

from src.npc.emotion import EmotionMachine, EmotionState, EMOTION_DECAY_TURNS
from src.npc.affinity import AffinityManager, AFFINITY_LEVELS, BEHAVIOR_MODIFIERS


# ===========================================================================
# EmotionMachine tests
# ===========================================================================

class TestEmotionMachine:
    """Tests for the EmotionMachine state machine."""

    @pytest.fixture
    def machine(self) -> EmotionMachine:
        return EmotionMachine()

    def test_initial_state_is_neutral(self, machine: EmotionMachine):
        assert machine.current_emotion == EmotionState.NEUTRAL

    # --- Positive sentiment transitions ---

    def test_positive_high_intensity_general_becomes_happy(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="positive", intensity=0.8, intent="general_chat"
        )
        assert result.new_emotion == EmotionState.HAPPY
        assert result.affinity_delta > 0
        assert machine.current_emotion == EmotionState.HAPPY

    def test_positive_high_intensity_quest_becomes_excited(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="positive", intensity=0.8, intent="quest_inquiry"
        )
        assert result.new_emotion == EmotionState.EXCITED
        assert result.affinity_delta == 15

    def test_positive_low_intensity_stays_neutral(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="positive", intensity=0.3, intent="general_chat"
        )
        assert result.new_emotion == EmotionState.NEUTRAL

    # --- Negative sentiment transitions ---

    def test_negative_very_high_intensity_becomes_angry(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="negative", intensity=0.9, intent="general_chat"
        )
        assert result.new_emotion == EmotionState.ANGRY
        assert result.affinity_delta < 0

    def test_negative_high_intensity_becomes_annoyed(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="negative", intensity=0.7, intent="general_chat"
        )
        assert result.new_emotion == EmotionState.ANNOYED
        assert result.affinity_delta == -10

    def test_negative_low_intensity_stays_neutral(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="negative", intensity=0.3, intent="general_chat"
        )
        assert result.new_emotion == EmotionState.NEUTRAL

    # --- Provocation ---

    def test_provocation_becomes_suspicious(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="neutral", intensity=0.5, intent="provocation"
        )
        assert result.new_emotion == EmotionState.SUSPICIOUS
        assert result.affinity_delta < 0

    # --- Repeated questions ---

    def test_repeated_question_becomes_annoyed(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="neutral", intensity=0.5, intent="general_chat", is_repeated=True
        )
        assert result.new_emotion == EmotionState.ANNOYED
        assert result.affinity_delta == -3

    # --- Cooldown mechanics ---

    def test_cooldown_reduces_affinity_change(self, machine: EmotionMachine):
        """Same trigger within 3 turns should reduce affinity change by 50%."""
        # First trigger
        result1 = machine.update(
            sentiment="positive", intensity=0.8, intent="general_chat"
        )
        first_delta = result1.affinity_delta

        # Tick once
        machine.tick()

        # Second same trigger (within 3 turns)
        result2 = machine.update(
            sentiment="positive", intensity=0.8, intent="general_chat"
        )
        # Should be reduced by cooldown
        assert abs(result2.affinity_delta) <= abs(first_delta)

    def test_cooldown_zeroes_after_many_repeats(self, machine: EmotionMachine):
        """Multiple repeats within 3 turns should zero out affinity change."""
        machine.update(sentiment="positive", intensity=0.8, intent="general_chat")
        machine.tick()
        machine.update(sentiment="positive", intensity=0.8, intent="general_chat")
        machine.tick()
        result = machine.update(
            sentiment="positive", intensity=0.8, intent="general_chat"
        )
        assert result.affinity_delta == 0

    # --- Decay mechanics ---

    def test_light_emotion_decays_after_3_turns(self, machine: EmotionMachine):
        """HAPPY should decay to NEUTRAL after 3 ticks."""
        machine.update(sentiment="positive", intensity=0.8, intent="general_chat")
        assert machine.current_emotion == EmotionState.HAPPY

        for _ in range(3):
            decay_result = machine.tick()

        assert machine.current_emotion == EmotionState.NEUTRAL
        assert decay_result is not None
        assert decay_result.new_emotion == EmotionState.NEUTRAL

    def test_heavy_emotion_decays_after_5_turns(self, machine: EmotionMachine):
        """ANGRY should decay to NEUTRAL after 5 ticks."""
        machine.update(sentiment="negative", intensity=0.9, intent="general_chat")
        assert machine.current_emotion == EmotionState.ANGRY

        for i in range(5):
            decay_result = machine.tick()

        assert machine.current_emotion == EmotionState.NEUTRAL
        assert decay_result is not None

    def test_neutral_does_not_decay(self, machine: EmotionMachine):
        """Ticking while neutral should not produce a decay event."""
        for _ in range(10):
            result = machine.tick()
            assert result is None

    @pytest.mark.parametrize(
        "emotion,expected_turns",
        [
            (EmotionState.HAPPY, 3),
            (EmotionState.ANNOYED, 3),
            (EmotionState.SAD, 3),
            (EmotionState.EXCITED, 3),
            (EmotionState.ANGRY, 5),
            (EmotionState.SUSPICIOUS, 5),
        ],
    )
    def test_decay_turn_counts(self, emotion: EmotionState, expected_turns: int):
        assert EMOTION_DECAY_TURNS[emotion] == expected_turns

    # --- Emotion change result ---

    def test_emotion_change_contains_reason(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="positive", intensity=0.8, intent="general_chat"
        )
        assert result.reason != ""

    def test_emotion_change_tracks_previous(self, machine: EmotionMachine):
        result = machine.update(
            sentiment="positive", intensity=0.8, intent="general_chat"
        )
        assert result.previous_emotion == EmotionState.NEUTRAL
        assert result.new_emotion == EmotionState.HAPPY


# ===========================================================================
# AffinityManager tests
# ===========================================================================

class TestAffinityManager:
    """Tests for the AffinityManager."""

    @pytest.fixture
    def manager(self) -> AffinityManager:
        return AffinityManager()

    def test_initial_value_is_15(self, manager: AffinityManager):
        assert manager.value == 15

    def test_custom_initial_value(self):
        mgr = AffinityManager(initial_value=50)
        assert mgr.value == 50

    # --- Bounds checking ---

    def test_cannot_go_below_zero(self, manager: AffinityManager):
        manager.update(-100)
        assert manager.value == 0

    def test_cannot_go_above_100(self, manager: AffinityManager):
        manager.update(200)
        assert manager.value == 100

    def test_initial_clamps_to_bounds(self):
        assert AffinityManager(initial_value=-10).value == 0
        assert AffinityManager(initial_value=150).value == 100

    # --- Update ---

    def test_positive_update(self, manager: AffinityManager):
        new_val = manager.update(10)
        assert new_val == 25
        assert manager.value == 25

    def test_negative_update(self, manager: AffinityManager):
        new_val = manager.update(-5)
        assert new_val == 10
        assert manager.value == 10

    def test_zero_update_no_change(self, manager: AffinityManager):
        new_val = manager.update(0)
        assert new_val == 15

    # --- Level labels ---

    @pytest.mark.parametrize(
        "affinity_value,expected_level",
        [
            (0, "낯선 사람"),
            (10, "낯선 사람"),
            (20, "낯선 사람"),
            (21, "아는 사이"),
            (30, "아는 사이"),
            (40, "아는 사이"),
            (41, "친구"),
            (50, "친구"),
            (60, "친구"),
            (61, "절친"),
            (80, "절친"),
            (81, "맹우"),
            (100, "맹우"),
        ],
    )
    def test_level_labels(self, affinity_value: int, expected_level: str):
        mgr = AffinityManager(initial_value=affinity_value)
        assert mgr.get_level() == expected_level

    # --- Behavior modifiers ---

    def test_stranger_behavior_modifiers(self):
        mgr = AffinityManager(initial_value=10)
        mods = mgr.get_behavior_modifiers()
        assert mods["basic_greeting"] is True
        assert mods["quest_hints"] is False
        assert mods["lore_secrets"] is False
        assert mods["info_depth"] == "minimal"

    def test_friend_behavior_modifiers(self):
        mgr = AffinityManager(initial_value=50)
        mods = mgr.get_behavior_modifiers()
        assert mods["quest_hints"] is True
        assert mods["lore_secrets"] is True
        assert mods["discounts"] is True
        assert mods["hidden_quests"] is False
        assert mods["info_depth"] == "detailed"

    def test_best_friend_behavior_modifiers(self):
        mgr = AffinityManager(initial_value=90)
        mods = mgr.get_behavior_modifiers()
        assert mods["companion"] is True
        assert mods["hidden_quests"] is True
        assert mods["special_items"] is True
        assert mods["info_depth"] == "full"

    def test_behavior_modifiers_change_with_level(self):
        """Verify that behavior modifiers update when affinity level changes."""
        mgr = AffinityManager(initial_value=10)
        mods_before = mgr.get_behavior_modifiers()
        assert mods_before["quest_hints"] is False

        mgr.update(30)  # Now at 40 -> "아는 사이"
        mods_after = mgr.get_behavior_modifiers()
        assert mods_after["quest_hints"] is True

    def test_behavior_modifiers_returns_copy(self):
        """Modifying returned dict should not affect the source."""
        mgr = AffinityManager(initial_value=50)
        mods = mgr.get_behavior_modifiers()
        mods["quest_hints"] = False
        assert mgr.get_behavior_modifiers()["quest_hints"] is True


# ===========================================================================
# PersonaLoader tests (parsing NPC markdown)
# ===========================================================================

class TestPersonaParser:
    """Tests for parsing NPC persona from markdown."""

    def test_chunker_parses_npc_sections(self, sample_npc_persona: str):
        """MarkdownSectionChunker should correctly parse NPC persona sections."""
        from src.rag.chunker import MarkdownSectionChunker

        chunker = MarkdownSectionChunker()
        metadata = {"doc_type": "npc", "doc_id": "blacksmith_garon"}
        chunks = chunker.chunk(sample_npc_persona, metadata)

        sections = [c.metadata["section"] for c in chunks]
        assert "기본 정보" in sections
        assert "성격" in sections
        assert "말투" in sections
        assert "지식 범위" in sections

    def test_npc_chunk_content_preserved(self, sample_npc_persona: str):
        from src.rag.chunker import MarkdownSectionChunker

        chunker = MarkdownSectionChunker()
        chunks = chunker.chunk(sample_npc_persona, {"doc_type": "npc", "doc_id": "test"})

        personality_chunks = [c for c in chunks if c.metadata["section"] == "성격"]
        assert len(personality_chunks) == 1
        assert "과묵하지만" in personality_chunks[0].content
