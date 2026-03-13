"""Document chunking strategies for different worldbuilding document types."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class Chunk:
    """A single chunk of text with associated metadata."""

    content: str
    metadata: dict[str, object] = field(default_factory=dict)


class BaseChunker(ABC):
    """Abstract base class for document chunkers."""

    @abstractmethod
    def chunk(self, text: str, metadata: dict[str, object]) -> list[Chunk]:
        """Split text into chunks with metadata."""
        ...


class MarkdownSectionChunker(BaseChunker):
    """Splits markdown documents by ## headers.

    Each section becomes a separate chunk, inheriting the parent document
    metadata plus the section name.
    """

    def chunk(self, text: str, metadata: dict[str, object]) -> list[Chunk]:
        sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        chunks: list[Chunk] = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            header_match = re.match(r"^## (.+)$", section, re.MULTILINE)
            section_name = header_match.group(1).strip() if header_match else "intro"

            chunk_metadata = {
                **metadata,
                "section": section_name,
            }
            chunks.append(Chunk(content=section, metadata=chunk_metadata))

        return chunks


class LoreChunker(BaseChunker):
    """Chunks lore documents using RecursiveCharacterTextSplitter.

    Uses 512 token chunks with 64 token overlap for general worldbuilding
    text (history, factions, magic system, geography).
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
        )

    def chunk(self, text: str, metadata: dict[str, object]) -> list[Chunk]:
        splits = self.splitter.split_text(text)
        chunks: list[Chunk] = []

        for i, split_text in enumerate(splits):
            chunk_metadata = {
                **metadata,
                "section": f"chunk_{i}",
            }
            chunks.append(Chunk(content=split_text, metadata=chunk_metadata))

        return chunks


class QuestChunker(BaseChunker):
    """Chunks quest documents by stage markers (## headers).

    Each stage gets a quest_stage metadata field for spoiler-prevention
    filtering based on player progress.
    """

    def chunk(self, text: str, metadata: dict[str, object]) -> list[Chunk]:
        sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
        chunks: list[Chunk] = []

        stage = 0
        for section in sections:
            section = section.strip()
            if not section:
                continue

            header_match = re.match(r"^## (.+)$", section, re.MULTILINE)
            section_name = header_match.group(1).strip() if header_match else "overview"

            if header_match:
                stage += 1

            chunk_metadata = {
                **metadata,
                "section": section_name,
                "quest_stage": stage,
            }
            chunks.append(Chunk(content=section, metadata=chunk_metadata))

        return chunks


class ItemChunker(BaseChunker):
    """Chunks item documents by individual item (### headers).

    Each item (weapon, armor, consumable) becomes a separate chunk
    for precise item-level retrieval.
    """

    def chunk(self, text: str, metadata: dict[str, object]) -> list[Chunk]:
        sections = re.split(r"(?=^### )", text, flags=re.MULTILINE)
        chunks: list[Chunk] = []

        # Handle content before the first ### header (e.g., document title, intro)
        preamble_parts = re.split(r"(?=^## )", sections[0], flags=re.MULTILINE) if sections else []
        for part in preamble_parts:
            part = part.strip()
            if not part:
                continue
            header_match = re.match(r"^## (.+)$", part, re.MULTILINE)
            section_name = header_match.group(1).strip() if header_match else "intro"
            chunk_metadata = {**metadata, "section": section_name}
            chunks.append(Chunk(content=part, metadata=chunk_metadata))

        # Handle each ### item section
        for section in sections[1:] if len(sections) > 1 else []:
            section = section.strip()
            if not section:
                continue

            header_match = re.match(r"^### (.+)$", section, re.MULTILINE)
            item_name = header_match.group(1).strip() if header_match else "unknown_item"

            chunk_metadata = {
                **metadata,
                "section": item_name,
            }
            chunks.append(Chunk(content=section, metadata=chunk_metadata))

        return chunks


class ChunkerFactory:
    """Factory that selects the appropriate chunker based on document type.

    Document types are inferred from the file path:
    - lore/     -> LoreChunker (RecursiveCharacterTextSplitter)
    - npcs/     -> MarkdownSectionChunker (## header-based)
    - quests/   -> QuestChunker (stage-based with quest_stage metadata)
    - items/    -> ItemChunker (### item-level splitting)
    """

    _chunkers: dict[str, BaseChunker] = {
        "lore": LoreChunker(),
        "npc": MarkdownSectionChunker(),
        "quest": QuestChunker(),
        "item": ItemChunker(),
    }

    @classmethod
    def get_chunker(cls, doc_type: str) -> BaseChunker:
        """Return the chunker for the given document type.

        Args:
            doc_type: One of 'lore', 'npc', 'quest', 'item'.

        Returns:
            Appropriate BaseChunker instance.

        Raises:
            ValueError: If doc_type is not recognized.
        """
        chunker = cls._chunkers.get(doc_type)
        if chunker is None:
            raise ValueError(
                f"Unknown doc_type '{doc_type}'. "
                f"Supported types: {list(cls._chunkers.keys())}"
            )
        return chunker

    @staticmethod
    def detect_doc_type(file_path: str | Path) -> str:
        """Detect document type from the file path.

        Args:
            file_path: Path to the markdown file, relative to worldbuilding/.

        Returns:
            Document type string: 'lore', 'npc', 'quest', or 'item'.
        """
        path_str = str(file_path).replace("\\", "/").lower()

        if "/npcs/" in path_str or path_str.startswith("npcs/"):
            return "npc"
        elif "/quests/" in path_str or path_str.startswith("quests/"):
            return "quest"
        elif "/items/" in path_str or path_str.startswith("items/"):
            return "item"
        elif "/lore/" in path_str or path_str.startswith("lore/"):
            return "lore"
        else:
            return "lore"  # Default fallback

    @staticmethod
    def build_metadata(
        file_path: str | Path,
        doc_type: str,
        related_ids: Optional[list[str]] = None,
    ) -> dict[str, object]:
        """Build base metadata for a document.

        Args:
            file_path: Path to the source file relative to worldbuilding/.
            doc_type: Document type string.
            related_ids: List of related document IDs for cross-referencing.

        Returns:
            Metadata dictionary.
        """
        path = Path(file_path)
        doc_id = path.stem  # filename without extension

        return {
            "doc_type": doc_type,
            "doc_id": doc_id,
            "source_file": str(file_path).replace("\\", "/"),
            "related_ids": related_ids or [],
        }
