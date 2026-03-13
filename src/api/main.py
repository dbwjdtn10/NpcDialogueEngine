"""FastAPI application entry point with lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.npc.persona import NPCPersona, PersonaLoader
from src.quest.tracker import QuestTracker
from src.rag.evaluator import RAGEvaluator
from src.rag.ingestion import IngestionPipeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application-level state (populated during startup)
# ---------------------------------------------------------------------------
_persona_registry: dict[str, NPCPersona] = {}
_quest_tracker: QuestTracker = QuestTracker()
_evaluator: RAGEvaluator = RAGEvaluator()


def get_persona_registry() -> dict[str, NPCPersona]:
    """Return the global NPC persona registry."""
    return _persona_registry


def set_persona_registry(personas: dict[str, NPCPersona]) -> None:
    """Replace the global NPC persona registry (used by hot-reload)."""
    global _persona_registry
    _persona_registry = personas


def get_quest_tracker() -> QuestTracker:
    """Return the global quest tracker instance."""
    return _quest_tracker


def get_evaluator() -> RAGEvaluator:
    """Return the global RAG evaluator instance."""
    return _evaluator


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup/shutdown."""
    global _persona_registry

    logger.info("Starting NPC Dialogue Engine...")

    # 1. Initialize ChromaDB / run ingestion if needed
    try:
        pipeline = IngestionPipeline()
        collection = pipeline.collection
        doc_count = collection.count()
        if doc_count == 0:
            logger.info("ChromaDB collection is empty, running ingestion...")
            pipeline.run()
        else:
            logger.info("ChromaDB collection has %d documents.", doc_count)
    except Exception as e:
        logger.warning("ChromaDB initialization skipped: %s", e)

    # 2. Load NPC personas from worldbuilding markdown
    try:
        _persona_registry = PersonaLoader.load_all()
        logger.info("Loaded %d NPC personas.", len(_persona_registry))
    except Exception as e:
        logger.warning("Persona loading failed: %s", e)

    # 3. Initialize database tables
    try:
        from src.db.database import create_tables
        await create_tables()
    except Exception as e:
        logger.warning("Database table creation skipped: %s", e)

    logger.info("NPC Dialogue Engine startup complete.")

    yield

    # Shutdown
    logger.info("Shutting down NPC Dialogue Engine...")

    try:
        from src.db.database import dispose_engine
        await dispose_engine()
    except Exception as e:
        logger.warning("Database engine disposal failed: %s", e)

    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NPC Dialogue Engine",
        description="AI-powered NPC dialogue system with RAG, emotion, and quest integration.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS middleware for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    from src.api.middleware import register_middleware
    register_middleware(app)

    # Include routers
    from src.api.routes.chat import router as chat_router
    from src.api.routes.npc import router as npc_router
    from src.api.routes.quest import router as quest_router
    from src.api.routes.admin import router as admin_router

    app.include_router(chat_router)
    app.include_router(npc_router)
    app.include_router(quest_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "npcs_loaded": str(len(_persona_registry)),
        }

    return app


app = create_app()
