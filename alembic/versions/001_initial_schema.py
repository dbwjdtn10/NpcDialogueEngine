"""Initial schema: users, npcs, affinities, sessions, messages, quests, logs.

Revision ID: 001
Revises: None
Create Date: 2025-01-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- npcs ---
    op.create_table(
        "npcs",
        sa.Column("npc_id", sa.String(128), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("occupation", sa.String(128), server_default=""),
        sa.Column("location", sa.String(256), server_default=""),
        sa.Column("personality_summary", sa.Text, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # --- user_npc_affinities ---
    op.create_table(
        "user_npc_affinities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "npc_id",
            sa.String(128),
            sa.ForeignKey("npcs.npc_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer, server_default="15"),
        sa.Column("level", sa.String(32), server_default="낯선 사람"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_affinity_user_npc",
        "user_npc_affinities",
        ["user_id", "npc_id"],
        unique=True,
    )

    # --- dialogue_sessions ---
    op.create_table(
        "dialogue_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "npc_id",
            sa.String(128),
            sa.ForeignKey("npcs.npc_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_session_user_npc",
        "dialogue_sessions",
        ["user_id", "npc_id"],
    )

    # --- dialogue_messages ---
    op.create_table(
        "dialogue_messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("dialogue_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("emotion", sa.String(32), nullable=True),
        sa.Column("affinity_delta", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_message_session_created",
        "dialogue_messages",
        ["session_id", "created_at"],
    )

    # --- quest_progress ---
    op.create_table(
        "quest_progress",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(64),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quest_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(256), server_default=""),
        sa.Column("status", sa.String(32), server_default="not_started"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("current_stage", sa.Integer, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_quest_user_quest",
        "quest_progress",
        ["user_id", "quest_id"],
        unique=True,
    )

    # --- affinity_logs ---
    op.create_table(
        "affinity_logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "affinity_id",
            sa.String(64),
            sa.ForeignKey("user_npc_affinities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delta", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(256), server_default=""),
        sa.Column("old_score", sa.Integer, nullable=False),
        sa.Column("new_score", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_affinity_log_record",
        "affinity_logs",
        ["affinity_id"],
    )


def downgrade() -> None:
    op.drop_table("affinity_logs")
    op.drop_table("quest_progress")
    op.drop_table("dialogue_messages")
    op.drop_table("dialogue_sessions")
    op.drop_table("user_npc_affinities")
    op.drop_table("npcs")
    op.drop_table("users")
