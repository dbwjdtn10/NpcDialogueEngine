"""Emotion state machine for NPCs with cooldown and decay mechanics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class EmotionState(str, Enum):
    """Possible NPC emotion states."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    ANNOYED = "annoyed"
    SAD = "sad"
    EXCITED = "excited"
    ANGRY = "angry"
    SUSPICIOUS = "suspicious"


# Light emotions decay after 3 turns, heavy emotions after 5 turns
EMOTION_DECAY_TURNS: dict[EmotionState, int] = {
    EmotionState.NEUTRAL: 0,
    EmotionState.HAPPY: 3,
    EmotionState.ANNOYED: 3,
    EmotionState.SAD: 3,
    EmotionState.EXCITED: 3,
    EmotionState.ANGRY: 5,
    EmotionState.SUSPICIOUS: 5,
}


@dataclass
class EmotionChange:
    """Result of an emotion state update."""

    previous_emotion: EmotionState
    new_emotion: EmotionState
    affinity_delta: int
    reason: str = ""


@dataclass
class CooldownEntry:
    """Tracks a trigger for cooldown purposes."""

    trigger_type: str
    turn_used: int


class EmotionMachine:
    """NPC emotion state machine with cooldown and turn-based decay.

    Features:
    - State transitions based on sentiment, intensity, intent, and repetition
    - Cooldown: same trigger within 3 turns = 50% affinity reduction, 5 turns = 0
    - Decay: light emotions revert to neutral after 3 turns, heavy after 5
    """

    def __init__(self, initial_emotion: EmotionState = EmotionState.NEUTRAL) -> None:
        self.current_emotion: EmotionState = initial_emotion
        self.turn_counter: int = 0
        self.turns_since_emotion_change: int = 0
        self.cooldown_history: list[CooldownEntry] = []

    def _get_cooldown_factor(self, trigger_type: str) -> float:
        """Calculate the affinity multiplier based on cooldown history.

        Returns:
            1.0 = no cooldown, 0.5 = 3-turn cooldown, 0.0 = 5-turn cooldown
        """
        recent_same = [
            entry
            for entry in self.cooldown_history
            if entry.trigger_type == trigger_type
            and (self.turn_counter - entry.turn_used) <= 5
        ]

        if len(recent_same) == 0:
            return 1.0

        # Check how many times this trigger fired within 5 turns
        within_3 = sum(
            1
            for entry in recent_same
            if (self.turn_counter - entry.turn_used) <= 3
        )

        if within_3 >= 2:
            return 0.0  # 5-turn equivalent: too many repeats
        elif within_3 >= 1:
            return 0.5  # 3-turn cooldown
        elif len(recent_same) >= 2:
            return 0.0

        return 0.5

    def update(
        self,
        sentiment: str,
        intensity: float,
        intent: str,
        is_repeated: bool = False,
    ) -> EmotionChange:
        """Update the emotion state based on user interaction analysis.

        Args:
            sentiment: "positive", "negative", or "neutral"
            intensity: Sentiment intensity from 0.0 to 1.0
            intent: User intent classification string
            is_repeated: Whether the user repeated a similar question

        Returns:
            EmotionChange with previous/new state and affinity delta.
        """
        previous = self.current_emotion
        new_emotion = previous
        affinity_delta = 0
        reason = ""

        # Determine trigger type for cooldown tracking
        trigger_type = f"{sentiment}_{intent}"

        # Determine emotion transition
        if is_repeated:
            new_emotion = EmotionState.ANNOYED
            affinity_delta = -3
            reason = "반복 질문"
            trigger_type = "repeated"

        elif sentiment == "positive" and intensity > 0.6:
            if intent == "quest_inquiry":
                new_emotion = EmotionState.EXCITED
                affinity_delta = 15
                reason = "퀘스트 완료 보고"
            else:
                new_emotion = EmotionState.HAPPY
                affinity_delta = 5
                reason = "긍정적 상호작용"

        elif sentiment == "negative" and intensity > 0.8:
            new_emotion = EmotionState.ANGRY
            affinity_delta = -20
            reason = "강한 부정적 상호작용"

        elif sentiment == "negative" and intensity > 0.6:
            new_emotion = EmotionState.ANNOYED
            affinity_delta = -10
            reason = "부정적 상호작용"

        elif intent == "provocation":
            new_emotion = EmotionState.SUSPICIOUS
            affinity_delta = -5
            reason = "도발/적대적 발언"

        # Apply cooldown to affinity change
        cooldown_factor = self._get_cooldown_factor(trigger_type)
        affinity_delta = int(affinity_delta * cooldown_factor)

        # Record cooldown entry
        self.cooldown_history.append(
            CooldownEntry(trigger_type=trigger_type, turn_used=self.turn_counter)
        )

        # Clean up old cooldown entries (older than 10 turns)
        self.cooldown_history = [
            entry
            for entry in self.cooldown_history
            if (self.turn_counter - entry.turn_used) <= 10
        ]

        # Update emotion state
        if new_emotion != previous:
            self.current_emotion = new_emotion
            self.turns_since_emotion_change = 0
        else:
            # Same emotion triggered again resets the decay counter
            if new_emotion != EmotionState.NEUTRAL:
                self.turns_since_emotion_change = 0

        return EmotionChange(
            previous_emotion=previous,
            new_emotion=self.current_emotion,
            affinity_delta=affinity_delta,
            reason=reason,
        )

    def tick(self) -> Optional[EmotionChange]:
        """Advance the turn counter and apply emotion decay if needed.

        Returns:
            EmotionChange if emotion decayed to neutral, None otherwise.
        """
        self.turn_counter += 1
        self.turns_since_emotion_change += 1

        if self.current_emotion == EmotionState.NEUTRAL:
            return None

        decay_turns = EMOTION_DECAY_TURNS.get(self.current_emotion, 3)

        if self.turns_since_emotion_change >= decay_turns:
            previous = self.current_emotion
            self.current_emotion = EmotionState.NEUTRAL
            self.turns_since_emotion_change = 0

            logger.debug(
                "Emotion decayed: %s -> neutral after %d turns",
                previous.value,
                decay_turns,
            )

            return EmotionChange(
                previous_emotion=previous,
                new_emotion=EmotionState.NEUTRAL,
                affinity_delta=0,
                reason=f"{previous.value} 감정 자연 소멸 ({decay_turns}턴)",
            )

        return None
