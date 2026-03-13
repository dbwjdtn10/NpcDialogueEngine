"""RAG quality evaluator using LLM-as-judge methodology."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of a single evaluation metric."""

    metric: str
    score: float
    details: str = ""


@dataclass
class EvaluationSummary:
    """Aggregated evaluation report."""

    faithfulness: float = 0.0
    relevance: float = 0.0
    context_recall: float = 0.0
    total_queries: int = 0
    results: list[EvaluationResult] = field(default_factory=list)


FAITHFULNESS_PROMPT = """당신은 응답의 충실도를 평가하는 심판입니다.
주어진 소스 문서를 기반으로, 응답이 소스의 정보만을 사용하고 있는지 평가하세요.

소스 문서:
{sources}

응답:
{response}

다음 JSON 형식으로만 응답하세요:
{{"score": 0.0~1.0, "reason": "평가 근거"}}

점수 기준:
- 1.0: 응답의 모든 내용이 소스에 근거함
- 0.7: 대부분 소스에 근거하나 일부 추론 포함
- 0.5: 소스 기반이지만 상당한 추론/확장 포함
- 0.3: 소스와 무관한 내용이 다수
- 0.0: 소스와 완전히 무관한 응답"""

RELEVANCE_PROMPT = """당신은 검색 결과의 관련성을 평가하는 심판입니다.
사용자 질문에 대해 검색된 문서들이 얼마나 관련 있는지 평가하세요.

사용자 질문:
{query}

검색된 문서:
{documents}

다음 JSON 형식으로만 응답하세요:
{{"score": 0.0~1.0, "reason": "평가 근거"}}

점수 기준:
- 1.0: 모든 문서가 질문에 직접 관련됨
- 0.7: 대부분 관련되나 일부 불필요한 문서 포함
- 0.5: 관련 문서와 무관한 문서가 섞임
- 0.3: 대부분 무관하나 일부 관련 문서 존재
- 0.0: 모든 문서가 질문과 무관"""


class RAGEvaluator:
    """Evaluates RAG pipeline quality using LLM-as-judge scoring.

    Provides faithfulness, relevance, and context recall metrics to
    monitor and improve retrieval and generation quality.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.LLM_MODEL
        self._llm: Optional[ChatGoogleGenerativeAI] = None
        self._results: list[EvaluationResult] = []

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        if self._llm is None:
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.0,
            )
        return self._llm

    def _parse_score_response(self, response_text: str) -> tuple[float, str]:
        """Parse a JSON score response from the LLM judge.

        Returns:
            Tuple of (score, reason).
        """
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        try:
            result = json.loads(text)
            score = float(result.get("score", 0.0))
            reason = result.get("reason", "")
            return max(0.0, min(1.0, score)), reason
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse evaluation response: %s", e)
            return 0.0, f"Parse error: {e}"

    async def evaluate_faithfulness(
        self,
        response: str,
        sources: list[str],
    ) -> EvaluationResult:
        """Evaluate whether a response is faithful to its source documents.

        Uses LLM-as-judge to score how well the response sticks to the
        information present in the provided sources.

        Args:
            response: The generated NPC response.
            sources: List of source document texts used for generation.

        Returns:
            EvaluationResult with faithfulness score.
        """
        sources_text = "\n---\n".join(sources) if sources else "(소스 없음)"
        prompt = FAITHFULNESS_PROMPT.format(sources=sources_text, response=response)

        try:
            llm_response = await self.llm.ainvoke(
                [
                    SystemMessage(content="당신은 공정한 품질 평가 심판입니다."),
                    HumanMessage(content=prompt),
                ]
            )
            score, reason = self._parse_score_response(llm_response.content)
        except Exception as e:
            logger.error("Faithfulness evaluation failed: %s", e)
            score, reason = 0.0, f"Evaluation error: {e}"

        result = EvaluationResult(
            metric="faithfulness", score=score, details=reason
        )
        self._results.append(result)
        return result

    async def evaluate_relevance(
        self,
        query: str,
        retrieved_docs: list[str],
    ) -> EvaluationResult:
        """Evaluate the relevance of retrieved documents to a query.

        Args:
            query: The user's original query.
            retrieved_docs: List of retrieved document texts.

        Returns:
            EvaluationResult with relevance score.
        """
        docs_text = "\n---\n".join(
            f"[문서 {i + 1}] {doc}" for i, doc in enumerate(retrieved_docs)
        )
        prompt = RELEVANCE_PROMPT.format(query=query, documents=docs_text)

        try:
            llm_response = await self.llm.ainvoke(
                [
                    SystemMessage(content="당신은 공정한 품질 평가 심판입니다."),
                    HumanMessage(content=prompt),
                ]
            )
            score, reason = self._parse_score_response(llm_response.content)
        except Exception as e:
            logger.error("Relevance evaluation failed: %s", e)
            score, reason = 0.0, f"Evaluation error: {e}"

        result = EvaluationResult(
            metric="relevance", score=score, details=reason
        )
        self._results.append(result)
        return result

    async def evaluate_context_recall(
        self,
        query: str,
        retrieved_docs: list[str],
        expected_docs: list[str],
    ) -> EvaluationResult:
        """Evaluate context recall by checking coverage of expected documents.

        Uses simple text overlap to measure what fraction of expected
        reference documents were captured by the retriever.

        Args:
            query: The user's query.
            retrieved_docs: List of actually retrieved document texts.
            expected_docs: List of expected/ground-truth document texts.

        Returns:
            EvaluationResult with recall score.
        """
        if not expected_docs:
            result = EvaluationResult(
                metric="context_recall",
                score=1.0,
                details="No expected documents provided.",
            )
            self._results.append(result)
            return result

        # Compute recall as fraction of expected docs found in retrieved set
        retrieved_combined = " ".join(retrieved_docs).lower()
        found = 0
        for expected in expected_docs:
            # Check if a significant portion of the expected doc appears
            expected_words = set(expected.lower().split())
            if not expected_words:
                continue
            overlap = sum(
                1 for w in expected_words if w in retrieved_combined
            )
            coverage = overlap / len(expected_words)
            if coverage >= 0.5:
                found += 1

        recall = found / len(expected_docs)

        result = EvaluationResult(
            metric="context_recall",
            score=recall,
            details=f"Found {found}/{len(expected_docs)} expected documents.",
        )
        self._results.append(result)
        return result

    async def run_evaluation(self, eval_dataset_path: str) -> EvaluationSummary:
        """Run batch evaluation from a JSON dataset file.

        Expected JSON format::

            [
                {
                    "query": "user question",
                    "response": "generated response",
                    "sources": ["source doc 1", ...],
                    "expected_docs": ["expected doc 1", ...]
                },
                ...
            ]

        Args:
            eval_dataset_path: Path to the evaluation dataset JSON file.

        Returns:
            EvaluationSummary with aggregated metrics.
        """
        path = Path(eval_dataset_path)
        if not path.exists():
            logger.error("Evaluation dataset not found: %s", path)
            return EvaluationSummary()

        with open(path, encoding="utf-8") as f:
            dataset: list[dict[str, Any]] = json.load(f)

        faithfulness_scores: list[float] = []
        relevance_scores: list[float] = []
        recall_scores: list[float] = []

        for entry in dataset:
            query = entry.get("query", "")
            response = entry.get("response", "")
            sources = entry.get("sources", [])
            expected = entry.get("expected_docs", [])

            faith = await self.evaluate_faithfulness(response, sources)
            faithfulness_scores.append(faith.score)

            rel = await self.evaluate_relevance(query, sources)
            relevance_scores.append(rel.score)

            rec = await self.evaluate_context_recall(query, sources, expected)
            recall_scores.append(rec.score)

        summary = EvaluationSummary(
            faithfulness=(
                sum(faithfulness_scores) / len(faithfulness_scores)
                if faithfulness_scores
                else 0.0
            ),
            relevance=(
                sum(relevance_scores) / len(relevance_scores)
                if relevance_scores
                else 0.0
            ),
            context_recall=(
                sum(recall_scores) / len(recall_scores)
                if recall_scores
                else 0.0
            ),
            total_queries=len(dataset),
            results=list(self._results),
        )

        logger.info(
            "Evaluation complete: %d queries, faithfulness=%.3f, "
            "relevance=%.3f, recall=%.3f",
            summary.total_queries,
            summary.faithfulness,
            summary.relevance,
            summary.context_recall,
        )

        return summary

    def generate_report(self) -> dict[str, Any]:
        """Generate an aggregate metrics report from accumulated results.

        Returns:
            Dictionary with per-metric averages and details.
        """
        metrics: dict[str, list[float]] = {}
        for result in self._results:
            metrics.setdefault(result.metric, []).append(result.score)

        report: dict[str, Any] = {
            "total_evaluations": len(self._results),
            "metrics": {},
        }

        for metric_name, scores in metrics.items():
            avg = sum(scores) / len(scores) if scores else 0.0
            report["metrics"][metric_name] = {
                "average": round(avg, 4),
                "count": len(scores),
                "min": round(min(scores), 4) if scores else 0.0,
                "max": round(max(scores), 4) if scores else 0.0,
            }

        return report
