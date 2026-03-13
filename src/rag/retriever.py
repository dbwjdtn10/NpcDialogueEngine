"""Hybrid retriever combining vector search (ChromaDB) and BM25 keyword search."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import chromadb
from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single retrieval result with content, metadata, and score."""

    content: str
    metadata: dict[str, object]
    score: float
    source: str = ""  # "vector", "bm25", or "hybrid"


class HybridRetriever:
    """Combines ChromaDB vector search with BM25 keyword search.

    Uses kiwipiepy for Korean morphological tokenization in BM25,
    and multilingual-e5-large embeddings for vector search.
    Results are combined with configurable weights (default 70/30).
    """

    def __init__(
        self,
        chroma_persist_dir: Optional[str] = None,
        embedding_model_name: Optional[str] = None,
        collection_name: str = "worldbuilding",
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> None:
        self.chroma_persist_dir = chroma_persist_dir or settings.CHROMA_PERSIST_DIR
        self.embedding_model_name = embedding_model_name or settings.EMBEDDING_MODEL
        self.collection_name = collection_name
        self.vector_weight = vector_weight if vector_weight is not None else settings.VECTOR_SEARCH_WEIGHT
        self.bm25_weight = bm25_weight if bm25_weight is not None else settings.BM25_SEARCH_WEIGHT
        self.top_k = top_k if top_k is not None else settings.TOP_K

        self._embedding_model: Optional[SentenceTransformer] = None
        self._chroma_client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None
        self._kiwi: Optional[Kiwi] = None

        # BM25 index state (built lazily from collection contents)
        self._bm25_index: Optional[BM25Okapi] = None
        self._bm25_documents: list[dict] = []
        self._bm25_built: bool = False

    @property
    def embedding_model(self) -> SentenceTransformer:
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(self.embedding_model_name)
        return self._embedding_model

    @property
    def chroma_client(self) -> chromadb.ClientAPI:
        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(
                path=self.chroma_persist_dir
            )
        return self._chroma_client

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            self._collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    @property
    def kiwi(self) -> Kiwi:
        if self._kiwi is None:
            self._kiwi = Kiwi()
        return self._kiwi

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text using Kiwi Korean morphological analyzer.

        Extracts content morphemes (nouns, verbs, adjectives) for BM25.
        """
        result = self.kiwi.tokenize(text)
        # Filter for content-bearing morphemes (NNG, NNP, VV, VA, etc.)
        content_tags = {"NNG", "NNP", "NNB", "VV", "VA", "MAG", "SL"}
        tokens = [token.form for token in result if token.tag in content_tags]
        return tokens

    def _build_bm25_index(self, doc_type_filter: Optional[str] = None) -> None:
        """Build the BM25 index from the ChromaDB collection.

        Args:
            doc_type_filter: If provided, only include documents of this type.
        """
        # Fetch all documents from the collection
        all_data = self.collection.get(include=["documents", "metadatas"])

        if not all_data["documents"]:
            self._bm25_built = True
            return

        documents = all_data["documents"]
        metadatas = all_data["metadatas"] or [{}] * len(documents)
        ids = all_data["ids"]

        # Filter by doc_type if specified
        filtered_docs: list[dict] = []
        tokenized_corpus: list[list[str]] = []

        for doc_id, doc, meta in zip(ids, documents, metadatas):
            if doc_type_filter and meta.get("doc_type") != doc_type_filter:
                continue
            tokens = self.tokenize(doc)
            if tokens:
                filtered_docs.append({
                    "id": doc_id,
                    "content": doc,
                    "metadata": meta,
                })
                tokenized_corpus.append(tokens)

        if tokenized_corpus:
            self._bm25_index = BM25Okapi(tokenized_corpus)
        else:
            self._bm25_index = None

        self._bm25_documents = filtered_docs
        self._bm25_built = True

    def _vector_search(
        self,
        query: str,
        top_k: int,
        doc_type_filter: Optional[str] = None,
    ) -> list[RetrievalResult]:
        """Perform vector similarity search using ChromaDB."""
        query_embedding = self.embedding_model.encode(
            f"query: {query}", show_progress_bar=False
        ).tolist()

        where_filter = None
        if doc_type_filter:
            where_filter = {"doc_type": doc_type_filter}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        retrieval_results: list[RetrievalResult] = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                # ChromaDB returns distances; convert cosine distance to similarity
                similarity = 1.0 - distance
                retrieval_results.append(
                    RetrievalResult(
                        content=doc,
                        metadata=meta or {},
                        score=similarity,
                        source="vector",
                    )
                )

        return retrieval_results

    def _bm25_search(
        self,
        query: str,
        top_k: int,
        doc_type_filter: Optional[str] = None,
    ) -> list[RetrievalResult]:
        """Perform BM25 keyword search using Kiwi tokenizer."""
        if not self._bm25_built:
            self._build_bm25_index(doc_type_filter)

        if self._bm25_index is None or not self._bm25_documents:
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25_index.get_scores(query_tokens)

        # Get top-K indices
        scored_indices = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]

        results: list[RetrievalResult] = []
        max_score = max(scores) if max(scores) > 0 else 1.0

        for idx, score in scored_indices:
            if score <= 0:
                continue
            doc = self._bm25_documents[idx]
            normalized_score = score / max_score  # Normalize to 0-1

            results.append(
                RetrievalResult(
                    content=doc["content"],
                    metadata=doc["metadata"],
                    score=normalized_score,
                    source="bm25",
                )
            )

        return results

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        doc_type_filter: Optional[str] = None,
    ) -> list[RetrievalResult]:
        """Perform hybrid retrieval combining vector and BM25 search.

        Args:
            query: The search query string.
            top_k: Number of results to return (defaults to settings.TOP_K).
            doc_type_filter: Filter results by document type (lore/npc/quest/item).

        Returns:
            List of RetrievalResult objects sorted by combined score.
        """
        k = top_k or self.top_k

        # Rebuild BM25 index if doc_type filter changes
        self._bm25_built = False

        # Fetch more candidates from each source to improve fusion quality
        candidate_k = k * 3

        vector_results = self._vector_search(query, candidate_k, doc_type_filter)
        bm25_results = self._bm25_search(query, candidate_k, doc_type_filter)

        # Merge results using weighted scores
        merged: dict[str, RetrievalResult] = {}

        for result in vector_results:
            key = result.content[:200]  # Use content prefix as dedup key
            weighted_score = result.score * self.vector_weight
            if key in merged:
                merged[key].score += weighted_score
            else:
                merged[key] = RetrievalResult(
                    content=result.content,
                    metadata=result.metadata,
                    score=weighted_score,
                    source="hybrid",
                )

        for result in bm25_results:
            key = result.content[:200]
            weighted_score = result.score * self.bm25_weight
            if key in merged:
                merged[key].score += weighted_score
            else:
                merged[key] = RetrievalResult(
                    content=result.content,
                    metadata=result.metadata,
                    score=weighted_score,
                    source="hybrid",
                )

        # Sort by combined score and return top-K
        sorted_results = sorted(
            merged.values(), key=lambda r: r.score, reverse=True
        )

        return sorted_results[:k]
