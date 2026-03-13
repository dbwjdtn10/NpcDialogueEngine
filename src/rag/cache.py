"""Semantic cache for RAG responses using Redis and cosine similarity."""

from __future__ import annotations

import json
import logging
import struct
from typing import Optional

import numpy as np
import redis.asyncio as aioredis

from src.config import settings

logger = logging.getLogger(__name__)

# Redis key prefixes
_CACHE_INDEX_PREFIX = "sem_cache:index:"
_CACHE_DATA_PREFIX = "sem_cache:data:"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def _encode_embedding(embedding: list[float]) -> bytes:
    """Pack a float list into compact bytes for Redis storage."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def _decode_embedding(data: bytes) -> list[float]:
    """Unpack bytes back into a float list."""
    n = len(data) // 4  # 4 bytes per float32
    return list(struct.unpack(f"{n}f", data))


class SemanticCache:
    """Redis-backed semantic cache for NPC dialogue responses.

    Caches responses keyed by NPC ID and query embedding.  On lookup the
    cache computes cosine similarity between the incoming query embedding
    and all stored embeddings for that NPC, returning a cached response
    when the similarity exceeds a configurable threshold.

    This avoids redundant LLM calls for semantically identical questions.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        threshold: Optional[float] = None,
        default_ttl: int = 3600,
    ) -> None:
        self.redis_url = redis_url or settings.REDIS_URL
        self.threshold = threshold if threshold is not None else settings.SEMANTIC_CACHE_THRESHOLD
        self.default_ttl = default_ttl
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=False)
        return self._redis

    async def get(
        self,
        npc_id: str,
        query_embedding: list[float],
        threshold: Optional[float] = None,
    ) -> Optional[str]:
        """Look up a cached response by semantic similarity.

        Args:
            npc_id: The NPC identifier to scope the cache.
            query_embedding: The embedding vector of the user query.
            threshold: Similarity threshold override (defaults to instance setting).

        Returns:
            Cached response string if a match is found above the threshold,
            otherwise ``None``.
        """
        sim_threshold = threshold if threshold is not None else self.threshold
        r = await self._get_redis()
        index_key = f"{_CACHE_INDEX_PREFIX}{npc_id}"

        # Get all cache entry IDs for this NPC
        entry_ids = await r.smembers(index_key)
        if not entry_ids:
            return None

        best_similarity = 0.0
        best_response: Optional[str] = None

        for entry_id in entry_ids:
            data_key = f"{_CACHE_DATA_PREFIX}{entry_id.decode()}"
            cached = await r.hgetall(data_key)

            if not cached:
                # Entry expired; clean up index
                await r.srem(index_key, entry_id)
                continue

            try:
                stored_embedding = _decode_embedding(cached[b"embedding"])
                similarity = _cosine_similarity(query_embedding, stored_embedding)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_response = cached[b"response"].decode("utf-8")
            except Exception as e:
                logger.warning("Failed to decode cache entry %s: %s", entry_id, e)
                continue

        if best_similarity >= sim_threshold and best_response is not None:
            logger.info(
                "Semantic cache HIT for npc=%s (similarity=%.4f)",
                npc_id,
                best_similarity,
            )
            return best_response

        return None

    async def set(
        self,
        npc_id: str,
        query_embedding: list[float],
        response: str,
        ttl: Optional[int] = None,
    ) -> None:
        """Store a response in the semantic cache.

        Args:
            npc_id: The NPC identifier to scope the cache.
            query_embedding: The embedding vector of the user query.
            response: The NPC response to cache.
            ttl: Time-to-live in seconds (defaults to ``default_ttl``).
        """
        import uuid

        entry_ttl = ttl if ttl is not None else self.default_ttl
        r = await self._get_redis()

        entry_id = f"{npc_id}:{uuid.uuid4().hex[:12]}"
        data_key = f"{_CACHE_DATA_PREFIX}{entry_id}"
        index_key = f"{_CACHE_INDEX_PREFIX}{npc_id}"

        await r.hset(
            data_key,
            mapping={
                "embedding": _encode_embedding(query_embedding),
                "response": response.encode("utf-8"),
                "npc_id": npc_id.encode("utf-8"),
            },
        )
        await r.expire(data_key, entry_ttl)
        await r.sadd(index_key, entry_id.encode("utf-8"))

        logger.debug("Semantic cache SET for npc=%s entry=%s", npc_id, entry_id)

    async def invalidate(self, npc_id: str) -> int:
        """Invalidate all cached entries for an NPC.

        Args:
            npc_id: The NPC identifier whose cache to clear.

        Returns:
            Number of entries removed.
        """
        r = await self._get_redis()
        index_key = f"{_CACHE_INDEX_PREFIX}{npc_id}"
        entry_ids = await r.smembers(index_key)

        count = 0
        for entry_id in entry_ids:
            data_key = f"{_CACHE_DATA_PREFIX}{entry_id.decode()}"
            await r.delete(data_key)
            count += 1

        await r.delete(index_key)
        logger.info("Invalidated %d cache entries for npc=%s", count, npc_id)
        return count

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
