"""Agent memory persistence models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel


class MemoryRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MemoryEntry(SQLModel, table=True):
    """Single memory entry for an agent.

    Stores conversational context, tool outputs, or any structured
    knowledge the agent should retain across invocations.
    """

    __tablename__ = "agent_memory"

    id: int | None = Field(default=None, primary_key=True)

    # Identity
    agent_id: str = Field(index=True, description="Logical agent identifier")
    session_id: str | None = Field(
        default=None, index=True, description="Conversation session"
    )

    # Content
    role: MemoryRole = MemoryRole.USER
    content: str = Field(max_length=65535)
    meta_data: dict | None = Field(default=None, sa_column=Column("metadata", JSON))

    # Ordering
    sequence_number: int = Field(ge=0, description="Order within session")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )

    # Composite index for efficient session queries
    __table_args__ = (
        Index(
            "ix_agent_memory_agent_session_sequence",
            "agent_id",
            "session_id",
            "sequence_number",
        ),
    )


class MemorySummary(SQLModel):
    """Projection for memory listing (no table)."""

    id: int
    agent_id: str
    session_id: str | None
    role: MemoryRole
    content_preview: str
    sequence_number: int
    created_at: datetime
