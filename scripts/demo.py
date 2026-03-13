"""CLI demo for chatting with an NPC in the terminal."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import logging
from src.config import settings
from src.npc.persona import PersonaLoader
from src.npc.dialogue import DialogueEngine


def select_npc(personas: dict) -> str:
    """Let the user select an NPC from the loaded personas."""
    npc_list = list(personas.items())

    print("\n사용 가능한 NPC:")
    print("-" * 40)
    for i, (npc_id, persona) in enumerate(npc_list, 1):
        print(f"  {i}. {persona.name} ({npc_id})")
    print("-" * 40)

    while True:
        try:
            choice = input("NPC 번호를 선택하세요: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(npc_list):
                return npc_list[idx][0]
            print("잘못된 번호입니다.")
        except ValueError:
            print("숫자를 입력하세요.")


def main() -> None:
    """Run the interactive CLI demo."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 60)
    print("  NPC Dialogue Engine - CLI Demo")
    print("=" * 60)

    # Load NPC personas
    print("\nNPC 페르소나 로딩 중...")
    personas = PersonaLoader.load_all()

    if not personas:
        print("NPC 페르소나를 찾을 수 없습니다.")
        print(f"worldbuilding/npcs/ 디렉토리를 확인하세요: {settings.WORLDBUILDING_DIR}")
        sys.exit(1)

    # Select NPC
    npc_id = select_npc(personas)
    persona = personas[npc_id]

    print(f"\n{persona.name}과(와)의 대화를 시작합니다.")
    print("종료하려면 'quit' 또는 'exit'를 입력하세요.\n")
    print("=" * 60)

    # Create dialogue engine
    engine = DialogueEngine(persona=persona)

    conversation_history: list[str] = []

    while True:
        try:
            user_input = input("\n[당신] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n대화를 종료합니다.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "종료"):
            print(f"\n{persona.name}: 다음에 또 보자.")
            break

        # Build short-term memory from recent conversation
        recent_context = "\n".join(conversation_history[-10:])

        # Generate response
        response = engine.generate(
            user_message=user_input,
            short_term_memory=recent_context,
        )

        # Display response
        print(f"\n[{persona.name}] > {response.message}")
        print(
            f"  (감정: {response.emotion} | "
            f"호감도: {response.affinity} [{response.affinity_level}] "
            f"({response.affinity_change:+d}) | "
            f"의도: {response.intent})"
        )

        if response.quest_trigger:
            print(f"  [퀘스트] {response.quest_trigger}")

        if response.emotion_change:
            print(f"  [감정 변화] {response.emotion_change}")

        # Update conversation history
        conversation_history.append(f"유저: {user_input}")
        conversation_history.append(f"{persona.name}: {response.message}")


if __name__ == "__main__":
    main()
