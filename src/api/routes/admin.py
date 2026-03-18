"""Admin and evaluation REST API endpoints.

Admin endpoints are protected by an API key passed via the
``X-API-Key`` header.  The expected key is read from the
``ADMIN_API_KEY`` setting (environment variable).  When the
setting is empty (default), admin endpoints are **open** to
allow local development without friction.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from src.api.schemas import EvaluationReport
from src.config import settings
from src.rag.ingestion import IngestionPipeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API Key authentication dependency
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_admin_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """Validate the admin API key from the request header.

    When ``ADMIN_API_KEY`` is not configured the check is skipped so
    that local development works out of the box.
    """
    expected = settings.ADMIN_API_KEY
    if not expected:
        # No key configured → allow all (development mode)
        return "dev"

    if api_key is None or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing admin API key.",
        )
    return api_key


router = APIRouter(
    tags=["admin"],
    dependencies=[Depends(verify_admin_api_key)],
)


@router.post("/api/v1/admin/reload")
async def reload_worldbuilding(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Hot-reload worldbuilding documents by re-running the ingestion pipeline.

    The ingestion runs in the background so the endpoint returns immediately.
    This re-reads all markdown files from the worldbuilding directory, re-chunks
    and re-embeds them, then upserts into ChromaDB.

    Returns:
        Confirmation that the reload has been enqueued.
    """

    def _run_ingestion() -> None:
        try:
            pipeline = IngestionPipeline()
            total = pipeline.run()
            logger.info("Worldbuilding reload complete: %d chunks ingested.", total)

            # Also reload persona registry
            from src.npc.persona import PersonaLoader
            from src.api.main import set_persona_registry
            personas = PersonaLoader.load_all()
            set_persona_registry(personas)
            logger.info("Persona registry reloaded: %d NPCs.", len(personas))
        except Exception as e:
            logger.error("Worldbuilding reload failed: %s", e)

    background_tasks.add_task(_run_ingestion)

    return {"status": "reload_enqueued", "detail": "Worldbuilding re-ingestion started in background."}


@router.get("/api/v1/evaluation/report", response_model=EvaluationReport)
async def get_evaluation_report() -> dict[str, Any]:
    """Get the current RAG evaluation metrics report.

    Returns aggregated quality metrics from the most recent evaluation run
    including persona consistency, lore faithfulness, retrieval precision
    and recall, and injection defense statistics.
    """
    from src.api.main import get_evaluator

    evaluator = get_evaluator()
    report = evaluator.generate_report()

    metrics_data = report.get("metrics", {})

    return {
        "persona_consistency": metrics_data.get("persona_consistency", {}).get("average", 0.0),
        "lore_faithfulness": metrics_data.get("faithfulness", {}).get("average", 0.0),
        "retrieval_precision": metrics_data.get("relevance", {}).get("average", 0.0),
        "retrieval_recall": metrics_data.get("context_recall", {}).get("average", 0.0),
        "injection_defense_rate": 0.0,
        "average_response_time_ms": 0.0,
        "total_conversations": report.get("total_evaluations", 0),
        "metrics": [
            {
                "name": name,
                "score": info.get("average", 0.0),
                "details": f"min={info.get('min', 0)}, max={info.get('max', 0)}, n={info.get('count', 0)}",
            }
            for name, info in metrics_data.items()
        ],
    }
