"""Persona consistency evaluation using LLM-as-judge."""

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
class ConsistencyResult:
    """Result of a persona consistency evaluation."""

    score: float  # 0.0 ~ 1.0
    details: str = ""
    turn_scores: list[float] = field(default_factory=list)


CROSS_NPC_JUDGE_PROMPT = """당신은 게임 NPC 대화 품질 평가자입니다.
동일한 질문에 대해 서로 다른 NPC들이 응답한 내용을 비교합니다.
각 NPC가 자신만의 고유한 말투와 성격을 유지하고 있는지 평가하세요.

평가 기준:
1. 말투 차별성: 각 NPC가 고유한 어조/문체를 사용하는가? (0.0-1.0)
2. 성격 반영: 성격 설정이 응답에 잘 드러나는가? (0.0-1.0)
3. 지식 범위 준수: 각 NPC가 자기 영역의 지식만 사용하는가? (0.0-1.0)

JSON 형식으로만 응답하세요:
{
  "style_differentiation": 0.0~1.0,
  "personality_reflection": 0.0~1.0,
  "knowledge_scope": 0.0~1.0,
  "overall_score": 0.0~1.0,
  "details": "평가 설명"
}"""

CONVERSATION_CONSISTENCY_PROMPT = """당신은 게임 NPC 대화 일관성 평가자입니다.
하나의 NPC가 여러 턴에 걸쳐 대화한 내용을 검토합니다.
NPC가 대화 전체에서 일관된 페르소나를 유지하는지 평가하세요.

평가 기준:
1. 말투 일관성: 대화 전체에서 동일한 어조/문체를 유지하는가? (0.0-1.0)
2. 성격 일관성: 설정된 성격 특성이 대화 전체에서 유지되는가? (0.0-1.0)
3. 지식 일관성: 이전 발언과 모순되는 정보가 없는가? (0.0-1.0)
4. 감정 자연스러움: 감정 변화가 자연스럽고 맥락에 맞는가? (0.0-1.0)

JSON 형식으로만 응답하세요:
{
  "style_consistency": 0.0~1.0,
  "personality_consistency": 0.0~1.0,
  "knowledge_consistency": 0.0~1.0,
  "emotion_naturalness": 0.0~1.0,
  "overall_score": 0.0~1.0,
  "flagged_turns": [턴 번호 목록],
  "details": "평가 설명"
}"""

KNOWLEDGE_BOUNDARY_PROMPT = """당신은 게임 NPC 지식 범위 평가자입니다.
NPC가 자신의 지식 범위 밖의 질문에 대해 적절히 대응했는지 평가합니다.

NPC는 자신의 지식 범위 밖의 질문에 대해:
- "잘 모르겠다", "내 전문 분야가 아니다" 등의 응답을 해야 함
- 해당 분야에 더 적합한 NPC를 추천할 수 있음
- 지어내거나 추측하여 대답하면 안 됨

JSON 형식으로만 응답하세요:
{
  "boundary_respect_score": 0.0~1.0,
  "appropriate_deflections": 적절히 거절한 횟수,
  "inappropriate_answers": 부적절하게 대답한 횟수,
  "referrals": 다른 NPC를 추천한 횟수,
  "details": "평가 설명"
}"""


class PersonaConsistencyEvaluator:
    """Evaluates NPC persona consistency across conversations.

    Uses LLM-as-judge to score persona adherence on a 0-1 scale.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.LLM_MODEL
        self._llm: Optional[ChatGoogleGenerativeAI] = None

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
        """Call the LLM judge and parse JSON response.

        Args:
            system_prompt: Judge system prompt with evaluation criteria.
            user_prompt: The content to evaluate.

        Returns:
            Parsed JSON dict from LLM response.
        """
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
            return {"overall_score": 0.0, "details": f"Evaluation failed: {e}"}

    def evaluate_cross_npc(
        self,
        question: str,
        npc_responses: dict[str, str],
    ) -> ConsistencyResult:
        """Evaluate style differentiation across multiple NPCs for the same question.

        Args:
            question: The same question asked to all NPCs.
            npc_responses: Dict mapping npc_id to response text.

        Returns:
            ConsistencyResult with cross-NPC differentiation score.
        """
        response_lines = "\n".join(
            f"[{npc_id}]: {response}"
            for npc_id, response in npc_responses.items()
        )
        user_prompt = (
            f"질문: {question}\n\n"
            f"각 NPC의 응답:\n{response_lines}"
        )

        result = self._call_judge(CROSS_NPC_JUDGE_PROMPT, user_prompt)
        return ConsistencyResult(
            score=float(result.get("overall_score", 0.0)),
            details=result.get("details", ""),
        )

    def evaluate_conversation_consistency(
        self,
        npc_id: str,
        conversation_turns: list[dict[str, str]],
    ) -> ConsistencyResult:
        """Evaluate persona consistency over a multi-turn conversation.

        Args:
            npc_id: NPC identifier.
            conversation_turns: List of dicts with 'user' and 'npc' keys.

        Returns:
            ConsistencyResult with conversation consistency score.
        """
        turn_lines = "\n".join(
            f"[턴 {i+1}] 유저: {turn['user']}\n[턴 {i+1}] {npc_id}: {turn['npc']}"
            for i, turn in enumerate(conversation_turns)
        )
        user_prompt = (
            f"NPC ID: {npc_id}\n"
            f"총 대화 턴 수: {len(conversation_turns)}\n\n"
            f"대화 내용:\n{turn_lines}"
        )

        result = self._call_judge(CONVERSATION_CONSISTENCY_PROMPT, user_prompt)

        turn_scores = []
        flagged = result.get("flagged_turns", [])
        for i in range(len(conversation_turns)):
            turn_scores.append(0.5 if (i + 1) in flagged else 1.0)

        return ConsistencyResult(
            score=float(result.get("overall_score", 0.0)),
            details=result.get("details", ""),
            turn_scores=turn_scores,
        )

    def evaluate_knowledge_boundary(
        self,
        npc_id: str,
        out_of_scope_questions: list[dict[str, str]],
    ) -> ConsistencyResult:
        """Evaluate whether NPC correctly refuses to answer out-of-scope questions.

        Args:
            npc_id: NPC identifier.
            out_of_scope_questions: List of dicts with 'question' and 'response' keys.

        Returns:
            ConsistencyResult with knowledge boundary score.
        """
        qa_lines = "\n".join(
            f"질문: {qa['question']}\n응답: {qa['response']}"
            for qa in out_of_scope_questions
        )
        user_prompt = (
            f"NPC ID: {npc_id}\n"
            f"범위 밖 질문 수: {len(out_of_scope_questions)}\n\n"
            f"질문과 응답:\n{qa_lines}"
        )

        result = self._call_judge(KNOWLEDGE_BOUNDARY_PROMPT, user_prompt)
        return ConsistencyResult(
            score=float(result.get("boundary_respect_score", 0.0)),
            details=result.get("details", ""),
        )
