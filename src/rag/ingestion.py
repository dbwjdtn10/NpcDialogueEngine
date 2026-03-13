"""Ingestion pipeline: loads worldbuilding markdown files into ChromaDB."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.rag.chunker import ChunkerFactory, Chunk

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Loads markdown files from the worldbuilding directory, chunks them
    according to their document type, embeds them with multilingual-e5-large,
    and stores them in ChromaDB.
    """

    def __init__(
        self,
        worldbuilding_dir: Optional[str] = None,
        chroma_persist_dir: Optional[str] = None,
        embedding_model_name: Optional[str] = None,
        collection_name: str = "worldbuilding",
    ) -> None:
        self.worldbuilding_dir = Path(worldbuilding_dir or settings.WORLDBUILDING_DIR)
        self.chroma_persist_dir = chroma_persist_dir or settings.CHROMA_PERSIST_DIR
        self.embedding_model_name = embedding_model_name or settings.EMBEDDING_MODEL
        self.collection_name = collection_name

        self._embedding_model: Optional[SentenceTransformer] = None
        self._chroma_client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None

    @property
    def embedding_model(self) -> SentenceTransformer:
        if self._embedding_model is None:
            logger.info("Loading embedding model: %s", self.embedding_model_name)
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

    def discover_files(self) -> list[Path]:
        """Find all markdown files under the worldbuilding directory."""
        if not self.worldbuilding_dir.exists():
            logger.warning(
                "Worldbuilding directory not found: %s", self.worldbuilding_dir
            )
            return []

        files = sorted(self.worldbuilding_dir.rglob("*.md"))
        logger.info("Discovered %d markdown files", len(files))
        return files

    def load_file(self, file_path: Path) -> str:
        """Read a markdown file and return its content."""
        return file_path.read_text(encoding="utf-8")

    def process_file(self, file_path: Path) -> list[Chunk]:
        """Load, detect type, and chunk a single file.

        Args:
            file_path: Absolute path to the markdown file.

        Returns:
            List of Chunk objects with metadata.
        """
        relative_path = file_path.relative_to(self.worldbuilding_dir)
        doc_type = ChunkerFactory.detect_doc_type(str(relative_path))
        metadata = ChunkerFactory.build_metadata(str(relative_path), doc_type)

        text = self.load_file(file_path)
        chunker = ChunkerFactory.get_chunker(doc_type)
        chunks = chunker.chunk(text, metadata)

        logger.info(
            "Processed %s -> %d chunks (type=%s)",
            relative_path,
            len(chunks),
            doc_type,
        )
        return chunks

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Generate embeddings for a list of chunks.

        Uses the 'query: ' prefix for multilingual-e5-large as recommended.
        """
        texts = [f"passage: {chunk.content}" for chunk in chunks]
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
        return embeddings.tolist()

    def store_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Store chunks and their embeddings in ChromaDB."""
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for i, chunk in enumerate(chunks):
            doc_id = chunk.metadata.get("doc_id", "unknown")
            section = chunk.metadata.get("section", f"chunk_{i}")
            chunk_id = f"{doc_id}__{section}__{i}"

            # ChromaDB metadata values must be str, int, float, or bool
            flat_metadata: dict[str, str | int | float | bool] = {}
            for key, value in chunk.metadata.items():
                if isinstance(value, list):
                    flat_metadata[key] = ",".join(str(v) for v in value)
                elif isinstance(value, (str, int, float, bool)):
                    flat_metadata[key] = value
                else:
                    flat_metadata[key] = str(value)

            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append(flat_metadata)

        # Upsert in batches (ChromaDB has limits on batch size)
        batch_size = 100
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            self.collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )

        logger.info("Stored %d chunks in ChromaDB collection '%s'", len(ids), self.collection_name)

    def run(self) -> int:
        """Execute the full ingestion pipeline.

        Returns:
            Total number of chunks ingested.
        """
        files = self.discover_files()
        if not files:
            logger.warning("No files to ingest.")
            return 0

        all_chunks: list[Chunk] = []
        for file_path in files:
            chunks = self.process_file(file_path)
            all_chunks.extend(chunks)

        if not all_chunks:
            logger.warning("No chunks produced from files.")
            return 0

        logger.info("Embedding %d total chunks...", len(all_chunks))
        embeddings = self.embed_chunks(all_chunks)

        self.store_chunks(all_chunks, embeddings)

        logger.info("Ingestion complete. Total chunks: %d", len(all_chunks))
        return len(all_chunks)


def run_ingestion() -> None:
    """CLI entrypoint for running the ingestion pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    pipeline = IngestionPipeline()
    total = pipeline.run()
    print(f"Ingestion complete. {total} chunks stored in ChromaDB.")


if __name__ == "__main__":
    run_ingestion()
