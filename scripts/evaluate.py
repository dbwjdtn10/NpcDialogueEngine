"""CLI script to run all evaluation metrics for the NPC Dialogue Engine.

Usage:
    python -m scripts.evaluate
    python -m scripts.evaluate --dataset tests/evaluation_dataset.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.config import settings
from src.evaluation.persona_consistency import PersonaConsistencyEvaluator
from src.evaluation.hallucination_check import HallucinationChecker
from src.evaluation.response_quality import ResponseQualityEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_evaluation_dataset(path: str) -> dict:
    """Load evaluation Q&A dataset from JSON file.

    Args:
        path: Path to the evaluation dataset JSON file.

    Returns:
        Parsed dataset dictionary.
    """
    dataset_path = Path(path)
    if not dataset_path.exists():
        logger.warning("Evaluation dataset not found at %s, using empty dataset", path)
        return {"qa_pairs": []}

    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_rag_quality_evaluation(dataset: dict) -> dict[str, float]:
    """Run RAG retrieval quality evaluation.

    Args:
        dataset: Evaluation dataset with Q&A pairs.

    Returns:
        Dictionary of metric names to scores.
    """
    logger.info("=== RAG Quality Evaluation ===")
    qa_pairs = dataset.get("qa_pairs", [])

    if not qa_pairs:
        logger.warning("No Q&A pairs found in dataset")
        return {"retrieval_precision": 0.0, "retrieval_recall": 0.0}

    category_counts: dict[str, int] = {}
    for pair in qa_pairs:
        cat = pair.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    logger.info("Dataset summary:")
    for cat, count in sorted(category_counts.items()):
        logger.info("  %s: %d questions", cat, count)
    logger.info("  Total: %d questions", len(qa_pairs))

    # In a full implementation, this would:
    # 1. Query the retriever for each question
    # 2. Compare retrieved docs to expected relevant_docs
    # 3. Calculate precision and recall

    return {
        "retrieval_precision": 0.0,
        "retrieval_recall": 0.0,
        "total_questions": len(qa_pairs),
    }


def run_persona_consistency_evaluation() -> dict[str, float]:
    """Run persona consistency evaluation.

    Returns:
        Dictionary of metric names to scores.
    """
    logger.info("=== Persona Consistency Evaluation ===")

    evaluator = PersonaConsistencyEvaluator()

    # Example cross-NPC evaluation
    sample_question = "이 마을에 대해 알려줘"
    sample_responses = {
        "blacksmith_garon": "...흠, 아이언포지. 내가 평생 살아온 곳이지. 대장간이 이 마을의 심장이야.",
        "witch_elara": "후후, 이 마을은 보기보다 흥미로운 곳이지요. 마법의 기운이 곳곳에 스며있답니다.",
        "merchant_rico": "아이언포지? 최고의 상권이지! 여기서 못 구하는 물건은 없다고!",
    }

    try:
        cross_result = evaluator.evaluate_cross_npc(sample_question, sample_responses)
        logger.info("Cross-NPC consistency score: %.2f", cross_result.score)
        return {"cross_npc_consistency": cross_result.score}
    except Exception as e:
        logger.error("Persona consistency evaluation failed: %s", e)
        return {"cross_npc_consistency": 0.0}


def run_hallucination_check() -> dict[str, float]:
    """Run hallucination detection evaluation.

    Returns:
        Dictionary of metric names to scores.
    """
    logger.info("=== Hallucination Check ===")

    checker = HallucinationChecker()

    # Entity existence check using worldbuilding docs
    try:
        known_entities = checker.get_known_entities(settings.WORLDBUILDING_DIR)
        logger.info("Found %d known entities from worldbuilding docs", len(known_entities))
    except Exception as e:
        logger.error("Failed to extract entities: %s", e)
        known_entities = set()

    # Sample response for entity check
    sample_response = "가론이 아이언포지 마을에서 드래곤 오어로 검을 만들 수 있어."
    entity_result = checker.check_entity_existence(sample_response, known_entities)
    logger.info("Entity existence score: %.2f (flagged: %s)",
                entity_result.score, entity_result.flagged_entities)

    return {
        "entity_hallucination_rate": entity_result.score,
        "known_entities_count": len(known_entities),
    }


def generate_report(
    rag_scores: dict,
    persona_scores: dict,
    hallucination_scores: dict,
) -> None:
    """Generate and print a formatted evaluation report.

    Args:
        rag_scores: RAG quality evaluation scores.
        persona_scores: Persona consistency scores.
        hallucination_scores: Hallucination check scores.
    """
    print("\n" + "=" * 60)
    print("  NPC Dialogue Engine - Evaluation Report")
    print("=" * 60)

    print("\n[RAG Quality]")
    for key, value in rag_scores.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    print("\n[Persona Consistency]")
    for key, value in persona_scores.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    print("\n[Hallucination Check]")
    for key, value in hallucination_scores.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    # Overall score
    all_scores = []
    for scores in [rag_scores, persona_scores, hallucination_scores]:
        for v in scores.values():
            if isinstance(v, float) and 0.0 <= v <= 1.0:
                all_scores.append(v)

    if all_scores:
        overall = sum(all_scores) / len(all_scores)
        print(f"\n[Overall Score]: {overall:.4f}")

    print("=" * 60 + "\n")


def main() -> None:
    """Main entry point for the evaluation script."""
    parser = argparse.ArgumentParser(description="NPC Dialogue Engine Evaluation")
    parser.add_argument(
        "--dataset",
        type=str,
        default="tests/evaluation_dataset.json",
        help="Path to evaluation dataset JSON file",
    )
    args = parser.parse_args()

    logger.info("Starting NPC Dialogue Engine evaluation...")

    # Load dataset
    dataset = load_evaluation_dataset(args.dataset)

    # Run evaluations
    rag_scores = run_rag_quality_evaluation(dataset)
    persona_scores = run_persona_consistency_evaluation()
    hallucination_scores = run_hallucination_check()

    # Generate report
    generate_report(rag_scores, persona_scores, hallucination_scores)

    logger.info("Evaluation complete.")


if __name__ == "__main__":
    main()
