"""Monitoring endpoints: detailed health checks and Prometheus metrics."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])


async def _check_redis() -> dict[str, Any]:
    """Verify Redis connectivity and measure round-trip latency."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        start = time.perf_counter()
        pong = await client.ping()
        latency_ms = (time.perf_counter() - start) * 1000
        await client.aclose()

        return {
            "status": "healthy" if pong else "unhealthy",
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return {"status": "unhealthy", "error": str(e)}


async def _check_postgres() -> dict[str, Any]:
    """Verify PostgreSQL connectivity via a lightweight query."""
    try:
        from sqlalchemy import text

        from src.db.database import async_session_factory

        start = time.perf_counter()
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        latency_ms = (time.perf_counter() - start) * 1000

        return {"status": "healthy", "latency_ms": round(latency_ms, 2)}
    except Exception as e:
        logger.warning("PostgreSQL health check failed: %s", e)
        return {"status": "unhealthy", "error": str(e)}


async def _check_chromadb() -> dict[str, Any]:
    """Verify ChromaDB is accessible and report document count."""
    try:
        import chromadb

        start = time.perf_counter()
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        collection = client.get_or_create_collection("worldbuilding")
        doc_count = collection.count()
        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "status": "healthy",
            "document_count": doc_count,
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        logger.warning("ChromaDB health check failed: %s", e)
        return {"status": "unhealthy", "error": str(e)}


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Deep health check probing all external dependencies.

    Returns the connectivity status and latency of Redis, PostgreSQL,
    and ChromaDB.  The overall status is ``healthy`` only when every
    dependency reports healthy.
    """
    from src.api.main import get_persona_registry

    redis_status = await _check_redis()
    postgres_status = await _check_postgres()
    chromadb_status = await _check_chromadb()

    all_healthy = all(
        dep["status"] == "healthy"
        for dep in [redis_status, postgres_status, chromadb_status]
    )

    persona_count = len(get_persona_registry())

    # Include circuit breaker states
    from src.api.circuit_breaker import redis_breaker, postgres_breaker, llm_breaker

    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": "0.1.0",
        "npcs_loaded": persona_count,
        "dependencies": {
            "redis": redis_status,
            "postgresql": postgres_status,
            "chromadb": chromadb_status,
        },
        "circuit_breakers": {
            "redis": redis_breaker.stats,
            "postgresql": postgres_breaker.stats,
            "llm_api": llm_breaker.stats,
        },
    }


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """Expose application metrics in Prometheus text exposition format.

    Scraped by Prometheus at the configured interval to populate
    dashboards and alerting rules.
    """
    from src.api.metrics import render_metrics

    return render_metrics()
