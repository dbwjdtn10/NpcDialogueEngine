"""WebSocket chat endpoint for real-time NPC dialogue."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.npc.affinity import AffinityManager
from src.npc.dialogue import DialogueEngine, DialogueResponse
from src.npc.emotion import EmotionMachine
from src.npc.memory import MemoryManager
from src.npc.persona import NPCPersona

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_fallback_response(npc_id: str) -> str:
    """Return an NPC-appropriate fallback response for error situations."""
    fallbacks: dict[str, str] = {
        "blacksmith_garon": "(가론이 망치를 내려놓고 잠시 생각에 잠긴다...)",
        "witch_elara": "(엘라라가 수정 구슬을 바라보며 중얼거린다...)",
        "merchant_rico": "(리코가 상품을 정리하며 잠시 말을 멈춘다...)",
        "guard_captain_thane": "(세인이 주변을 경계하며 잠시 침묵한다...)",
    }
    return fallbacks.get(npc_id, "(NPC가 잠시 생각에 잠깁니다...)")


@router.websocket("/ws/chat/{npc_id}")
async def websocket_chat(
    websocket: WebSocket,
    npc_id: str,
    user_id: str = Query(...),
) -> None:
    """WebSocket endpoint for real-time NPC dialogue.

    Connect to ``/ws/chat/{npc_id}?user_id=<uuid>`` and send JSON messages::

        {"message": "안녕하세요!"}

    The server streams back response tokens and a final complete message::

        {"type": "token", "content": "안"}
        {"type": "token", "content": "녕"}
        ...
        {"type": "complete", "data": { ... full ChatResponse ... }}

    On disconnect the session is summarized and archived to long-term memory.
    """
    await websocket.accept()

    # Import here to avoid circular imports at module level
    from src.api.main import get_persona_registry

    persona_registry = get_persona_registry()
    persona: Optional[NPCPersona] = persona_registry.get(npc_id)

    if persona is None:
        await websocket.send_json({
            "type": "error",
            "detail": f"NPC '{npc_id}' not found.",
        })
        await websocket.close(code=4004)
        return

    # Initialize session state
    session_id = str(uuid.uuid4())
    memory_manager = MemoryManager()
    affinity = AffinityManager()
    emotion = EmotionMachine()

    engine = DialogueEngine(
        persona=persona,
        affinity=affinity,
        emotion=emotion,
    )

    # Load memory context
    memory_ctx = await memory_manager.get_context_for_prompt(
        user_id=user_id, npc_id=npc_id, session_id=session_id
    )

    await websocket.send_json({
        "type": "session_start",
        "session_id": session_id,
        "npc_id": npc_id,
        "npc_name": persona.name,
        "emotion": emotion.current_emotion.value,
        "affinity": affinity.value,
        "affinity_level": affinity.get_level(),
    })

    logger.info(
        "WebSocket session started: session=%s user=%s npc=%s",
        session_id, user_id, npc_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()

            if not user_message:
                await websocket.send_json({
                    "type": "error",
                    "detail": "Empty message.",
                })
                continue

            # Store user message in short-term memory
            await memory_manager.short_term.store_message(
                session_id, "user", user_message
            )

            # Refresh context
            memory_ctx = await memory_manager.get_context_for_prompt(
                user_id=user_id, npc_id=npc_id, session_id=session_id
            )

            try:
                # Run the full dialogue pipeline
                response: DialogueResponse = await engine.generate(
                    user_message=user_message,
                    short_term_memory=memory_ctx["short_term_memory"],
                    long_term_memory=memory_ctx["long_term_memory"],
                )

                # Stream tokens to simulate streaming output
                message_text = response.message
                for i, char in enumerate(message_text):
                    await websocket.send_json({
                        "type": "token",
                        "content": char,
                    })

                # Store NPC response in short-term memory
                await memory_manager.short_term.store_message(
                    session_id, "npc", response.message
                )

                # Send complete response with metadata
                response_data: dict[str, Any] = {
                    "type": "complete",
                    "data": {
                        "npc_id": response.npc_id,
                        "message": response.message,
                        "intent": response.intent,
                        "emotion": response.emotion,
                        "emotion_change": response.emotion_change,
                        "affinity": response.affinity,
                        "affinity_change": response.affinity_change,
                        "affinity_level": response.affinity_level,
                        "quest_trigger": response.quest_trigger,
                        "metadata": response.metadata,
                    },
                }
                await websocket.send_json(response_data)

            except Exception as e:
                logger.error(
                    "Dialogue pipeline error in session %s: %s",
                    session_id, e,
                )
                fallback = _get_fallback_response(npc_id)
                await websocket.send_json({
                    "type": "complete",
                    "data": {
                        "npc_id": npc_id,
                        "message": fallback,
                        "intent": "error",
                        "emotion": emotion.current_emotion.value,
                        "emotion_change": None,
                        "affinity": affinity.value,
                        "affinity_change": 0,
                        "affinity_level": affinity.get_level(),
                        "quest_trigger": None,
                        "metadata": {"error": str(e)},
                    },
                })

    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected: session=%s user=%s npc=%s",
            session_id, user_id, npc_id,
        )
    except Exception as e:
        logger.error("WebSocket error in session %s: %s", session_id, e)
    finally:
        # Trigger session summarization on disconnect
        try:
            await memory_manager.on_session_end(
                session_id=session_id,
                user_id=user_id,
                npc_id=npc_id,
            )
        except Exception as e:
            logger.error("Session summarization failed for %s: %s", session_id, e)

        await memory_manager.close()
        logger.info("Session %s cleanup complete.", session_id)
