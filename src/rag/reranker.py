"""Cross-encoder reranker for refining retrieval results."""

from __future__ import annotations

import logging
from typing import Optional

from sentence_transformers import CrossEncoder

from src.config import settings
from src.rag.retriever import RetrievalResult

logger = logging.getLogger(__name__)


class Reranker:
    """Reranks candidate documents using a cross-encoder model.

    Uses cross-encoder/ms-marco-multilingual-MiniLM-L12-v2 by default
    for multilingual (Korean + English) relevance scoring.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> None:
        self.model_name = model_name or settings.RERANKER_MODEL
        self.top_k = top_k if top_k is not None else settings.TOP_K
        self._model: Optional[CrossEncoder] = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            logger.info("Loading reranker model: %s", self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: Optional[int] = None,
    ) -> list[RetrievalResult]:
        """Rerank candidate documents by cross-encoder relevance score.

        Args:
            query: The original search query.
            candidates: List of RetrievalResult from the hybrid retriever.
            top_k: Number of top results to return after reranking.

        Returns:
            Reranked list of RetrievalResult, sorted by cross-encoder score.
        """
        if not candidates:
            return []

        k = top_k or self.top_k

        # Build query-document pairs for the cross-encoder
        pairs = [(query, candidate.content) for candidate in candidates]

        # Score all pairs
        scores = self.model.predict(pairs)

        # Attach reranker scores and sort
        scored_results: list[RetrievalResult] = []
        for candidate, score in zip(candidates, scores):
            scored_results.append(
                RetrievalResult(
                    content=candidate.content,
                    metadata=candidate.metadata,
                    score=float(score),
                    source="reranked",
                )
            )

        scored_results.sort(key=lambda r: r.score, reverse=True)

        logger.debug(
            "Reranked %d candidates -> top %d",
            len(candidates),
            min(k, len(scored_results)),
        )

        return scored_results[:k]
