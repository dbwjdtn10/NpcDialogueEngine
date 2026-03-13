"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings loaded from environment variables and .env file."""

    # LLM
    GEMINI_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # PostgreSQL
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/npc_dialogue"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Worldbuilding documents
    WORLDBUILDING_DIR: str = "./worldbuilding"

    # Embedding & Reranker models
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-multilingual-MiniLM-L12-v2"

    # Hybrid search weights
    VECTOR_SEARCH_WEIGHT: float = 0.7
    BM25_SEARCH_WEIGHT: float = 0.3

    # Retrieval
    TOP_K: int = 5

    # Semantic cache
    SEMANTIC_CACHE_THRESHOLD: float = 0.95

    # Session
    SESSION_TIMEOUT_MINUTES: int = 30

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
