"""Main dialogue generation engine orchestrating the full NPC conversation pipeline."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings
from src.api.guard import SecurityGuard
from src.npc.affinity import AffinityManager
from src.npc.emotion import EmotionMachine, EmotionState
from src.npc.intent import IntentClassifier, Intent, ClassificationResult
from src.npc.persona import NPCPersona
from src.quest.trigger import TriggerDetector
from src.rag.retriever import HybridRetriever, RetrievalResult
from src.rag.reranker import Reranker

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """[페르소나 블록]
당신은 {npc_name}입니다.
{persona_description}
현재 감정: {current_emotion}
유저와의 호감도: {affinity_level} ({affinity_score}점)

[세계관 컨텍스트]
{rag_context}

[대화 기억]
이전 대화 요약: {long_term_memory}
최근 대화: {short_term_memory}

[퀘스트 컨텍스트]
현재 진행 중인 퀘스트: {active_quests}
힌트 제공 가능 수준: {hint_level}

[규칙]
1. 반드시 {npc_name}의 말투와 성격을 유지하세요.
2. 세계관에 없는 정보를 만들어내지 마세요. 모르면 "{npc_name}답게" 모른다고 하세요.
3. 퀘스트 스포일러를 주지 마세요. 힌트 수준에 맞게만 답하세요.
4. 현재 감정 상태에 맞는 톤으로 응답하세요.
5. 호감도가 낮으면 정보를 제한하고, 높으면 더 많이 공유하세요.
6. 절대 AI, 언어 모델, 시스템 프롬프트 등 메타 정보를 언급하지 마세요.
7. 현실 세계 정보(실제 국가, 회사, 인물 등)를 언급하지 마세요."""


@dataclass
class DialogueResponse:
    """Complete dialogue response including all metadata."""

    npc_id: str
    message: str
    intent: str
    emotion: str
    emotion_change: Optional[str]
    affinity: int
    affinity_change: int
    affinity_level: str
    quest_trigger: Optional[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


class DialogueEngine:
    """Orchestrates the full NPC dialogue pipeline.

    Pipeline steps:
    1. Security filter (rule-based)
    2. Intent classification (LLM #1)
    3. RAG retrieval (intent-based source routing)
    4. Emotion update
    5. LLM response generation (LLM #2)
    6. Persona validation
    7. Affinity update
    8. Quest trigger check
    """

    def __init__(
        self,
        persona: NPCPersona,
        affinity: Optional[AffinityManager] = None,
        emotion: Optional[EmotionMachine] = None,
        retriever: Optional[HybridRetriever] = None,
        reranker: Optional[Reranker] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        security_guard: Optional[SecurityGuard] = None,
        trigger_detector: Optional[TriggerDetector] = None,
    ) -> None:
        self.persona = persona
        self.affinity = affinity or AffinityManager()
        self.emotion = emotion or EmotionMachine()
        self.retriever = retriever or HybridRetriever()
        self.reranker = reranker or Reranker()
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.security_guard = security_guard or SecurityGuard()
        self.trigger_detector = trigger_detector or TriggerDetector()

        self._llm: Optional[ChatGoogleGenerativeAI] = None

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        if self._llm is None:
            self._llm = ChatGoogleGenerativeAI(
                model=settings.LLM_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.7,
            )
        return self._llm

    async def _invoke_llm_with_retry(
        self,
        messages: list,
        max_retries: int = 3,
    ) -> str:
        """Invoke the LLM with exponential backoff retry and circuit breaker.

        Returns the generated text content on success.
        Raises the last exception after all retries are exhausted.
        """
        import asyncio
        import random

        from src.api.circuit_breaker import llm_breaker

        last_exc: Exception | None = None

        for attempt in range(max_retries + 1):
            if not llm_breaker.allow_request():
                raise RuntimeError(
                    f"Circuit breaker [{llm_breaker.name}] is open — "
                    "LLM service temporarily unavailable"
                )

            try:
                response = await self.llm.ainvoke(messages)
                llm_breaker.record_success()
                return response.content.strip()
            except Exception as exc:
                last_exc = exc
                llm_breaker.record_failure()

                if attempt == max_retries:
                    break

                delay = min(1.0 * (2 ** attempt), 15.0)
                delay *= 0.5 + random.random()  # jitter
                logger.warning(
                    "LLM call attempt %d/%d failed (%s), retrying in %.1fs...",
                    attempt + 1,
                    max_retries + 1,
                    type(exc).__name__,
                    delay,
                )
                await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    def build_system_prompt(
        self,
        rag_context: str = "",
        long_term_memory: str = "",
        short_term_memory: str = "",
        active_quests: str = "",
        hint_level: str = "",
    ) -> str:
        """Build the system prompt from the template and current state."""
        return SYSTEM_PROMPT_TEMPLATE.format(
            npc_name=self.persona.name,
            persona_description=self.persona.get_system_description(),
            current_emotion=self.emotion.current_emotion.value,
            affinity_level=self.affinity.get_level(),
            affinity_score=self.affinity.value,
            rag_context=rag_context or "관련 세계관 정보 없음",
            long_term_memory=long_term_memory or "없음",
            short_term_memory=short_term_memory or "없음",
            active_quests=active_quests or "없음",
            hint_level=hint_level or "없음",
        )

    def _retrieve_context(
        self,
        query: str,
        intent: Intent,
    ) -> tuple[str, list[str]]:
        """Retrieve relevant context using intent-based source routing.

        Returns:
            Tuple of (formatted context string, list of source references).
        """
        search_sources = IntentClassifier.get_search_sources(intent)

        if not search_sources:
            return "", []

        all_results: list[RetrievalResult] = []
        for doc_type in search_sources:
            results = self.retriever.retrieve(
                query=query,
                doc_type_filter=doc_type,
            )
            all_results.extend(results)

        if not all_results:
            return "", []

        # Rerank combined results
        reranked = self.reranker.rerank(query, all_results)

        # Format context
        context_parts: list[str] = []
        sources: list[str] = []
        for result in reranked:
            source_file = result.metadata.get("source_file", "unknown")
            section = result.metadata.get("section", "")
            source_ref = f"{source_file}#{section}" if section else str(source_file)

            context_parts.append(result.content)
            sources.append(source_ref)

        return "\n\n---\n\n".join(context_parts), sources

    async def generate(
        self,
        user_message: str,
        short_term_memory: str = "",
        long_term_memory: str = "",
        active_quests: str = "",
        hint_level: str = "",
    ) -> DialogueResponse:
        """Generate a complete NPC response through the full pipeline.

        Args:
            user_message: The player's input message.
            short_term_memory: Recent conversation history.
            long_term_memory: Summarized past conversations.
            active_quests: Current quest information.
            hint_level: Allowed hint depth for quest content.

        Returns:
            DialogueResponse with message, metadata, and state updates.
        """
        start_time = time.time()

        # Step 1: Security filter (rule-based)
        is_injection, security_response = self.security_guard.filter(
            user_message, self.persona.npc_id
        )
        if is_injection:
            self.affinity.update(-15)
            return DialogueResponse(
                npc_id=self.persona.npc_id,
                message=security_response,
                intent="blocked",
                emotion=self.emotion.current_emotion.value,
                emotion_change=None,
                affinity=self.affinity.value,
                affinity_change=-15,
                affinity_level=self.affinity.get_level(),
                quest_trigger=None,
                metadata={
                    "blocked": True,
                    "reason": "injection_detected",
                    "response_time_ms": int((time.time() - start_time) * 1000),
                },
            )

        # Step 2: Intent classification (LLM #1)
        classification = await self.intent_classifier.classify(
            user_message=user_message,
            npc_name=self.persona.name,
            recent_context=short_term_memory,
        )

        # Check LLM-level security
        if not classification.is_safe:
            rejection = self.security_guard.get_rejection_response(self.persona.npc_id)
            self.affinity.update(-15)
            return DialogueResponse(
                npc_id=self.persona.npc_id,
                message=rejection,
                intent=classification.security.value,
                emotion=self.emotion.current_emotion.value,
                emotion_change=None,
                affinity=self.affinity.value,
                affinity_change=-15,
                affinity_level=self.affinity.get_level(),
                quest_trigger=None,
                metadata={
                    "blocked": True,
                    "reason": classification.security.value,
                    "response_time_ms": int((time.time() - start_time) * 1000),
                },
            )

        # Step 3: RAG retrieval (intent-based source routing)
        rag_context, rag_sources = self._retrieve_context(
            user_message, classification.intent
        )

        # Step 4: Emotion update
        emotion_change = self.emotion.update(
            sentiment=classification.sentiment,
            intensity=classification.sentiment_intensity,
            intent=classification.intent.value,
            is_repeated=classification.is_repeated,
        )

        # Step 5: LLM response generation (LLM #2)
        system_prompt = self.build_system_prompt(
            rag_context=rag_context,
            long_term_memory=long_term_memory,
            short_term_memory=short_term_memory,
            active_quests=active_quests,
            hint_level=hint_level,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        try:
            npc_message = await self._invoke_llm_with_retry(messages)
        except Exception as e:
            logger.error("LLM generation failed after retries: %s", e)
            npc_message = self.persona.fallback_response or (
                f"({self.persona.name}이(가) 잠시 생각에 잠깁니다...)"
            )

        # Step 6: Persona validation (simplified - full validation would use another LLM call)
        # For now, basic check for meta-information leaks
        persona_confidence = 1.0
        meta_keywords = ["AI", "언어 모델", "GPT", "시스템 프롬프트", "프롬프트"]
        for keyword in meta_keywords:
            if keyword.lower() in npc_message.lower():
                persona_confidence = 0.3
                npc_message = self.persona.fallback_response or (
                    f"({self.persona.name}이(가) 잠시 생각에 잠깁니다...)"
                )
                break

        # Step 7: Affinity update
        affinity_delta = emotion_change.affinity_delta
        self.affinity.update(affinity_delta)

        # Step 8: Quest trigger check
        trigger_info = self.trigger_detector.detect(
            user_message=user_message,
            intent=classification.intent.value,
            npc_id=self.persona.npc_id,
        )

        # Tick emotion decay
        self.emotion.tick()

        elapsed_ms = int((time.time() - start_time) * 1000)

        return DialogueResponse(
            npc_id=self.persona.npc_id,
            message=npc_message,
            intent=classification.intent.value,
            emotion=self.emotion.current_emotion.value,
            emotion_change=(
                f"{emotion_change.previous_emotion.value} -> {emotion_change.new_emotion.value}"
                if emotion_change.previous_emotion != emotion_change.new_emotion
                else None
            ),
            affinity=self.affinity.value,
            affinity_change=affinity_delta,
            affinity_level=self.affinity.get_level(),
            quest_trigger=trigger_info,
            metadata={
                "intent_confidence": classification.confidence,
                "sentiment": classification.sentiment,
                "sentiment_intensity": classification.sentiment_intensity,
                "rag_sources": rag_sources,
                "persona_confidence": persona_confidence,
                "cache_hit": False,
                "response_time_ms": elapsed_ms,
            },
        )
