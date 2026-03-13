"""NPC Persona management: parsing and loading NPC profiles from markdown."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class NPCPersona:
    """Complete NPC persona definition loaded from worldbuilding markdown."""

    npc_id: str
    name: str
    age: str = ""
    race: str = ""
    occupation: str = ""
    location: str = ""
    personality: str = ""
    speech_style: str = ""
    knowledge_scope: list[str] = field(default_factory=list)
    relationships: dict[str, str] = field(default_factory=dict)
    quest_connections: list[str] = field(default_factory=list)
    current_emotion: str = "neutral"
    affinity: dict[str, int] = field(default_factory=dict)
    fallback_response: str = ""
    rejection_response: str = ""

    def get_system_description(self) -> str:
        """Generate a concise description for the LLM system prompt."""
        lines = [
            f"이름: {self.name}",
            f"나이: {self.age}" if self.age else "",
            f"종족: {self.race}" if self.race else "",
            f"직업: {self.occupation}" if self.occupation else "",
            f"위치: {self.location}" if self.location else "",
            f"성격: {self.personality}" if self.personality else "",
            f"말투: {self.speech_style}" if self.speech_style else "",
        ]
        return "\n".join(line for line in lines if line)


class PersonaLoader:
    """Parses NPC markdown files into NPCPersona objects.

    Expected markdown format:
        # NPC Name
        ## 기본 정보
        - 나이: ...
        - 종족: ...
        ...
        ## 성격
        ...
        ## 말투
        ...
        ## 관계
        ...
        ## 퀘스트 관련
        ...
    """

    @staticmethod
    def _extract_section(text: str, header: str) -> str:
        """Extract the content under a ## header section."""
        pattern = rf"^## {re.escape(header)}\s*\n(.*?)(?=^## |\Z)"
        match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _parse_list_items(section: str) -> dict[str, str]:
        """Parse '- key: value' lines into a dictionary."""
        items: dict[str, str] = {}
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                key, _, value = line[2:].partition(":")
                items[key.strip()] = value.strip()
        return items

    @staticmethod
    def _parse_name(text: str) -> str:
        """Extract the NPC name from the # title line."""
        match = re.match(r"^# (.+)$", text, re.MULTILINE)
        return match.group(1).strip() if match else ""

    @classmethod
    def parse(cls, file_path: Path) -> NPCPersona:
        """Parse a single NPC markdown file into an NPCPersona.

        Args:
            file_path: Path to the NPC markdown file.

        Returns:
            NPCPersona dataclass instance.
        """
        text = file_path.read_text(encoding="utf-8")
        npc_id = file_path.stem  # e.g. "blacksmith_garon"

        name = cls._parse_name(text)

        # Parse basic info section
        basic_info_text = cls._extract_section(text, "기본 정보")
        basic_info = cls._parse_list_items(basic_info_text)

        # Parse personality
        personality = cls._extract_section(text, "성격")

        # Parse speech style
        speech_style = cls._extract_section(text, "말투")

        # Parse relationships
        relationships_text = cls._extract_section(text, "관계")
        relationships = cls._parse_list_items(relationships_text)

        # Parse quest connections
        quest_text = cls._extract_section(text, "퀘스트 관련")
        quest_connections: list[str] = []
        for line in quest_text.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                quest_connections.append(line[2:].strip())

        return NPCPersona(
            npc_id=npc_id,
            name=name,
            age=basic_info.get("나이", ""),
            race=basic_info.get("종족", ""),
            occupation=basic_info.get("직업", ""),
            location=basic_info.get("위치", ""),
            personality=personality,
            speech_style=speech_style,
            relationships=relationships,
            quest_connections=quest_connections,
        )

    @classmethod
    def load_all(
        cls, worldbuilding_dir: Optional[str] = None
    ) -> dict[str, NPCPersona]:
        """Load all NPC personas from the worldbuilding/npcs/ directory.

        Args:
            worldbuilding_dir: Base worldbuilding directory path.

        Returns:
            Dictionary mapping npc_id to NPCPersona.
        """
        base_dir = Path(worldbuilding_dir or settings.WORLDBUILDING_DIR)
        npcs_dir = base_dir / "npcs"

        if not npcs_dir.exists():
            logger.warning("NPCs directory not found: %s", npcs_dir)
            return {}

        personas: dict[str, NPCPersona] = {}
        for md_file in sorted(npcs_dir.glob("*.md")):
            try:
                persona = cls.parse(md_file)
                personas[persona.npc_id] = persona
                logger.info("Loaded NPC persona: %s (%s)", persona.name, persona.npc_id)
            except Exception as e:
                logger.error("Failed to parse NPC file %s: %s", md_file, e)

        logger.info("Loaded %d NPC personas total", len(personas))
        return personas
