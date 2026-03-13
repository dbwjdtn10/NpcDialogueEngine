"""Hallucination detection for NPC responses."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class HallucinationResult:
    """Result of a hallucination check."""

    score: float  # 0.0 (no hallucination) ~ 1.0 (fully hallucinated)
    flagged_entities: list[str] = field(default_factory=list)
    details: str = ""
    is_faithful: bool = True


FAITHFULNESS_JUDGE_PROMPT = """당신은 게임 NPC 대화 시스템의 사실성 검증기입니다.
NPC의 응답이 제공된 RAG 소스 자료에 기반하여 정확한지 평가하세요.

평가 기준:
1. 소스 근거: 응답의 모든 주요 주장이 소스 자료에 근거하는가? (0.0-1.0)
2. 사실 왜곡: 소스의 정보를 왜곡하거나 변형한 부분이 있는가? (0.0-1.0, 높을수록 왜곡 적음)
3. 허위 추가: 소스에 없는 정보를 지어낸 부분이 있는가? (0.0-1.0, 높을수록 추가 없음)

JSON 형식으로만 응답하세요:
{
  "source_grounding": 0.0~1.0,
  "factual_accuracy": 0.0~1.0,
  "no_fabrication": 0.0~1.0,
  "overall_faithfulness": 0.0~1.0,
  "fabricated_claims": ["지어낸 주장 목록"],
  "details": "평가 설명"
}"""


class HallucinationChecker:
    """Checks NPC responses for hallucinations against RAG sources and known entities.

    Combines LLM-as-judge faithfulness scoring with string-match entity validation.
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

    def check_faithfulness(
        self,
        response: str,
        rag_sources: list[str],
    ) -> HallucinationResult:
        """Check if a response is grounded in the provided RAG sources using LLM judge.

        Args:
            response: The NPC response to check.
            rag_sources: List of source text chunks used to generate the response.

        Returns:
            HallucinationResult with faithfulness score.
        """
        sources_text = "\n---\n".join(rag_sources)
        user_prompt = (
            f"NPC 응답:\n{response}\n\n"
            f"RAG 소스 자료:\n{sources_text}"
        )

        messages = [
            SystemMessage(content=FAITHFULNESS_JUDGE_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        try:
            llm_response = self.llm.invoke(messages)
            text = llm_response.content.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            result = json.loads(text)

            faithfulness = float(result.get("overall_faithfulness", 0.0))
            fabricated = result.get("fabricated_claims", [])

            return HallucinationResult(
                score=1.0 - faithfulness,  # Higher = more hallucination
                flagged_entities=fabricated,
                details=result.get("details", ""),
                is_faithful=faithfulness >= 0.7,
            )
        except Exception as e:
            logger.error("Faithfulness check failed: %s", e)
            return HallucinationResult(
                score=0.5,
                details=f"Evaluation failed: {e}",
                is_faithful=False,
            )

    def check_entity_existence(
        self,
        response: str,
        known_entities: set[str],
    ) -> HallucinationResult:
        """Check if entity names in the response match known entities.

        Uses simple string matching to find entity names (NPC, place, item names)
        that appear in the response but are not in the known entities set.

        Args:
            response: The NPC response to check.
            known_entities: Set of all known entity names from worldbuilding docs.

        Returns:
            HallucinationResult with flagged unknown entities.
        """
        # Extract potential entity names (Korean proper nouns, capitalized English words)
        # Look for quoted names, parenthesized English names, and known patterns
        potential_entities: set[str] = set()

        # Match Korean names (2-6 chars that could be proper nouns)
        korean_patterns = [
            r"「(.+?)」",
            r"\'(.+?)\'",
            r"\"(.+?)\"",
        ]
        for pattern in korean_patterns:
            matches = re.findall(pattern, response)
            potential_entities.update(matches)

        # Match English capitalized words (potential entity names)
        english_names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", response)
        potential_entities.update(english_names)

        # Check which potential entities are not in known entities
        flagged: list[str] = []
        known_lower = {e.lower() for e in known_entities}

        for entity in potential_entities:
            entity_lower = entity.lower()
            # Check if entity or any known entity is a substring of the other
            found = False
            for known in known_lower:
                if entity_lower in known or known in entity_lower:
                    found = True
                    break
            if not found and len(entity) >= 2:
                flagged.append(entity)

        total_entities = len(potential_entities) if potential_entities else 1
        hallucination_ratio = len(flagged) / total_entities

        return HallucinationResult(
            score=hallucination_ratio,
            flagged_entities=flagged,
            details=f"Unknown entities: {flagged}" if flagged else "All entities verified",
            is_faithful=hallucination_ratio < 0.3,
        )

    @staticmethod
    def get_known_entities(worldbuilding_dir: str | Path) -> set[str]:
        """Extract all entity names from worldbuilding documents.

        Scans markdown files for proper nouns, NPC names, place names,
        and item names.

        Args:
            worldbuilding_dir: Path to the worldbuilding documents directory.

        Returns:
            Set of known entity name strings.
        """
        entities: set[str] = set()
        wb_path = Path(worldbuilding_dir)

        if not wb_path.exists():
            logger.warning("Worldbuilding directory not found: %s", worldbuilding_dir)
            return entities

        for md_file in wb_path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning("Failed to read %s: %s", md_file, e)
                continue

            # Extract from headers
            headers = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)
            for header in headers:
                # Clean up header text
                clean = header.strip()
                # Remove numbering like "1. " or "## "
                clean = re.sub(r"^\d+\.\s*", "", clean)
                if clean:
                    entities.add(clean)

            # Extract parenthesized English names
            english_names = re.findall(r"\(([A-Z][a-zA-Z\s]+)\)", content)
            entities.update(english_names)

            # Extract bold text (often entity names)
            bold_names = re.findall(r"\*\*(.+?)\*\*", content)
            for name in bold_names:
                # Skip common non-entity bold text
                if len(name) <= 20 and not name.startswith("등급"):
                    entities.add(name)

            # Extract names from "이름: " or "- 이름: " patterns
            name_patterns = re.findall(r"이름[:\s]+(.+?)(?:\n|$)", content)
            entities.update(name.strip() for name in name_patterns)

            # Add filename stems as entity IDs
            entities.add(md_file.stem)

        return entities
