"""CLI script to run the worldbuilding document ingestion pipeline."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.rag.ingestion import run_ingestion


def main() -> None:
    """Run the ingestion pipeline from the command line."""
    print("=" * 60)
    print("NPC Dialogue Engine - Worldbuilding Ingestion")
    print("=" * 60)
    run_ingestion()


if __name__ == "__main__":
    main()
