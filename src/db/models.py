"""SQLAlchemy ORM models for the NPC Dialogue Engine."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


class User(Base):
    """Player / user account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    affinities: Mapped[list[UserNPCAffinity]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[DialogueSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    quest_progress: Mapped[list[QuestProgress]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class NPC(Base):
    """NPC definition stored in the database."""

    __tablename__ = "npcs"

    npc_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    occupation: Mapped[str] = mapped_column(String(128), default="")
    location: Mapped[str] = mapped_column(String(256), default="")
    personality_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    affinities: Mapped[list[UserNPCAffinity]] = relationship(
        back_populates="npc", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[DialogueSession]] = relationship(
        back_populates="npc", cascade="all, delete-orphan"
    )


class UserNPCAffinity(Base):
    """Affinity score between a user and an NPC."""

    __tablename__ = "user_npc_affinities"
    __table_args__ = (
        Index("ix_affinity_user_npc", "user_id", "npc_id", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    npc_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("npcs.npc_id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, default=15)
    level: Mapped[str] = mapped_column(String(32), default="낯선 사람")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="affinities")
    npc: Mapped[NPC] = relationship(back_populates="affinities")
    logs: Mapped[list[AffinityLog]] = relationship(
        back_populates="affinity_record", cascade="all, delete-orphan"
    )


class DialogueSession(Base):
    """A single conversation session between a user and an NPC."""

    __tablename__ = "dialogue_sessions"
    __table_args__ = (
        Index("ix_session_user_npc", "user_id", "npc_id"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    npc_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("npcs.npc_id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="sessions")
    npc: Mapped[NPC] = relationship(back_populates="sessions")
    messages: Mapped[list[DialogueMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="DialogueMessage.created_at"
    )


class DialogueMessage(Base):
    """Individual message within a dialogue session."""

    __tablename__ = "dialogue_messages"
    __table_args__ = (
        Index("ix_message_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("dialogue_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" or "npc"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    emotion: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    affinity_delta: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    session: Mapped[DialogueSession] = relationship(back_populates="messages")


class QuestProgress(Base):
    """Player quest progress tracking."""

    __tablename__ = "quest_progress"
    __table_args__ = (
        Index("ix_quest_user_quest", "user_id", "quest_id", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    quest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="not_started")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="quest_progress")


class AffinityLog(Base):
    """Audit log for affinity score changes."""

    __tablename__ = "affinity_logs"
    __table_args__ = (
        Index("ix_affinity_log_record", "affinity_id"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    affinity_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_npc_affinities.id", ondelete="CASCADE"),
        nullable=False,
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), default="")
    old_score: Mapped[int] = mapped_column(Integer, nullable=False)
    new_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    affinity_record: Mapped[UserNPCAffinity] = relationship(back_populates="logs")
