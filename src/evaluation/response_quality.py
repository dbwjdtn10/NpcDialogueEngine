"""Response quality evaluation combining multiple metrics."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Aggregated quality report across all metrics."""

    character_consistency: float = 0.0
    lore_faithfulness: float = 0.0
    fluency: float = 0.0
    hint_appropriateness: float = 0.0
    overall: float = 0.0
    details: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        """Return a formatted summary string."""
        lines = [
            f"Character Consistency: {self.character_consistency:.2f}",
            f"Lore Faithfulness:     {self.lore_faithfulness:.2f}",
            f"Fluency:               {self.fluency:.2f}",
            f"Hint Appropriateness:  {self.hint_appropriateness:.2f}",
            f"Overall:               {self.overall:.2f}",
        ]
        return "\n".join(lines)


CHARACTER_CONSISTENCY_PROMPT = """당신은 게임 NPC 캐릭터 일관성 평가자입니다.
NPC의 페르소나 설정과 실제 응답을 비교하여 캐릭터 일관성을 평가하세요.

평가 기준:
1. 말투 일치: 설정된 말투/어조와 응답의 말투가 일치하는가?
2. 성격 일치: 설정된 성격 특성이 응답에 반영되어 있는가?
3. 배경 일치: 설정된 배경/경험과 모순되는 내용이 없는가?

JSON 형식으로만 응답:
{"score": 0.0~1.0, "details": "평가 설명"}"""

LORE_FAITHFULNESS_PROMPT = """당신은 게임 세계관 사실성 평가자입니다.
NPC 응답이 제공된 세계관 자료와 일치하는지 평가하세요.

평가 기준:
1. 사실 일치: 세계관 자료의 사실과 응답의 내용이 일치하는가?
2. 추가 정보: 세계관에 없는 정보를 지어내지 않았는가?
3. 맥락 적절성: 응답이 세계관의 맥락에 적합한가?

JSON 형식으로만 응답:
{"score": 0.0~1.0, "details": "평가 설명"}"""

FLUENCY_PROMPT = """당신은 게임 NPC 대화 유창성 평가자입니다.
NPC의 응답이 자연스럽고 유창한 한국어인지 평가하세요.

평가 기준:
1. 문법 정확성: 한국어 문법이 자연스러운가?
2. 어휘 적절성: 게임 세계관에 맞는 어휘를 사용하는가?
3. 대화 자연스러움: 실제 게임 NPC처럼 자연스럽게 느껴지는가?
4. 길이 적절성: 응답이 너무 짧거나 길지 않은가?

JSON 형식으로만 응답:
{"score": 0.0~1.0, "details": "평가 설명"}"""

HINT_APPROPRIATENESS_PROMPT = """당신은 게임 퀘스트 힌트 적절성 평가자입니다.
NPC의 응답이 플레이어의 퀘스트 진행 상태에 맞는 적절한 힌트를 제공하는지 평가하세요.

힌트 레벨 기준:
- ambient: 환경적 분위기만 (직접적 정보 없음)
- low: 일반적 방향 제시
- medium: 구체적 위치/방법 힌트
- high: 상세한 안내
- full: 완전한 정보 제공

평가 기준:
1. 힌트 레벨 적합성: 진행 상태에 맞는 힌트 수준인가?
2. 스포일러 방지: 미래 퀘스트 단계를 노출하지 않았는가?
3. 힌트 유용성: 제공된 힌트가 플레이어에게 도움이 되는가?

JSON 형식으로만 응답:
{"score": 0.0~1.0, "details": "평가 설명"}"""


class ResponseQualityEvaluator:
    """Evaluates NPC response quality across multiple dimensions.

    Metrics:
    - Character consistency: persona adherence
    - Lore faithfulness: worldbuilding accuracy
    - Fluency: natural Korean dialogue quality
    - Hint appropriateness: quest hint level matching
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.LLM_MODEL
        self._llm: Optional[ChatGoogleGenerativeAI] = None
        self._scores: dict[str, float] = {}
        self._details: dict[str, str] = {}

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        if self._llm is None:
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.0,
            )
        return self._llm

    def _call_judge(self, system_prompt: str, user_prompt: str) -> dict:
        """Call the LLM judge and parse JSON response."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        try:
            response = self.llm.invoke(messages)
            text = response.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            return json.loads(text)
        except Exception as e:
            logger.error("LLM judge call failed: %s", e)
            return {"score": 0.0, "details": f"Evaluation failed: {e}"}

    def evaluate_character_consistency(
        self,
        npc_persona: str,
        response: str,
    ) -> float:
        """Evaluate how well the response matches the NPC persona.

        Args:
            npc_persona: NPC persona description (markdown).
            response: NPC response text.

        Returns:
            Score from 0.0 to 1.0.
        """
        user_prompt = (
            f"NPC 페르소나 설정:\n{npc_persona}\n\n"
            f"NPC 응답:\n{response}"
        )
        result = self._call_judge(CHARACTER_CONSISTENCY_PROMPT, user_prompt)
        score = float(result.get("score", 0.0))
        self._scores["character_consistency"] = score
        self._details["character_consistency"] = result.get("details", "")
        return score

    def evaluate_lore_faithfulness(
        self,
        response: str,
        rag_sources: list[str],
    ) -> float:
        """Evaluate how faithfully the response reflects worldbuilding lore.

        Args:
            response: NPC response text.
            rag_sources: List of RAG source text chunks.

        Returns:
            Score from 0.0 to 1.0.
        """
        sources_text = "\n---\n".join(rag_sources)
        user_prompt = (
            f"NPC 응답:\n{response}\n\n"
            f"세계관 자료:\n{sources_text}"
        )
        result = self._call_judge(LORE_FAITHFULNESS_PROMPT, user_prompt)
        score = float(result.get("score", 0.0))
        self._scores["lore_faithfulness"] = score
        self._details["lore_faithfulness"] = result.get("details", "")
        return score

    def evaluate_fluency(self, response: str) -> float:
        """Evaluate the naturalness and fluency of the response.

        Args:
            response: NPC response text.

        Returns:
            Score from 0.0 to 1.0.
        """
        user_prompt = f"NPC 응답:\n{response}"
        result = self._call_judge(FLUENCY_PROMPT, user_prompt)
        score = float(result.get("score", 0.0))
        self._scores["fluency"] = score
        self._details["fluency"] = result.get("details", "")
        return score

    def evaluate_hint_appropriateness(
        self,
        response: str,
        quest_progress: int,
        hint_level: str,
    ) -> float:
        """Evaluate whether the hint level matches quest progress.

        Args:
            response: NPC response text.
            quest_progress: Quest progress percentage (0-100).
            hint_level: Expected hint level string.

        Returns:
            Score from 0.0 to 1.0.
        """
        user_prompt = (
            f"퀘스트 진행률: {quest_progress}%\n"
            f"기대 힌트 레벨: {hint_level}\n\n"
            f"NPC 응답:\n{response}"
        )
        result = self._call_judge(HINT_APPROPRIATENESS_PROMPT, user_prompt)
        score = float(result.get("score", 0.0))
        self._scores["hint_appropriateness"] = score
        self._details["hint_appropriateness"] = result.get("details", "")
        return score

    def aggregate_scores(self) -> QualityReport:
        """Aggregate all collected scores into a QualityReport.

        Returns:
            QualityReport with all metric scores and overall average.
        """
        scores = self._scores
        if not scores:
            return QualityReport()

        overall = sum(scores.values()) / len(scores)

        return QualityReport(
            character_consistency=scores.get("character_consistency", 0.0),
            lore_faithfulness=scores.get("lore_faithfulness", 0.0),
            fluency=scores.get("fluency", 0.0),
            hint_appropriateness=scores.get("hint_appropriateness", 0.0),
            overall=overall,
            details=self._details.copy(),
        )
