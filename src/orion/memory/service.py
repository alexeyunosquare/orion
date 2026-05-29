"""Agent memory service for CRUD and retrieval operations."""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from orion.memory.models import MemoryEntry, MemoryRole, MemorySummary

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for managing agent memory entries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        agent_id: str,
        content: str,
        *,
        session_id: str | None = None,
        role: MemoryRole = MemoryRole.USER,
        metadata: dict[str, Any] | None = None,
        sequence_number: int | None = None,
    ) -> MemoryEntry:
        """Add a memory entry.

        If sequence_number is not provided, auto-increment based on
        the existing count for this agent+session.
        """
        if sequence_number is None:
            result = await self.session.exec(
                select(col(MemoryEntry.sequence_number))
                .where(MemoryEntry.agent_id == agent_id)
                .where(MemoryEntry.session_id == session_id)
                .order_by(col(MemoryEntry.sequence_number).desc())
                .limit(1)
            )
            first = result.first()
            sequence_number = (first + 1) if first is not None else 0

        entry = MemoryEntry(
            agent_id=agent_id,
            session_id=session_id,
            role=role,
            content=content,
            meta_data=metadata or {},
            sequence_number=sequence_number,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        logger.info(
            "Memory added: agent=%s session=%s seq=%d role=%s",
            agent_id,
            session_id,
            sequence_number,
            role,
        )
        return entry

    async def get_context(
        self,
        agent_id: str,
        session_id: str | None = None,
        *,
        limit: int = 50,
        role: MemoryRole | None = None,
    ) -> list[MemorySummary]:
        """Retrieve recent memory entries for context reconstruction.

        Returns the most recent entries, optionally filtered by role.
        """
        query = (
            select(MemoryEntry)
            .where(MemoryEntry.agent_id == agent_id)
            .order_by(col(MemoryEntry.sequence_number).desc())
            .limit(limit)
        )

        if session_id is not None:
            query = query.where(MemoryEntry.session_id == session_id)

        if role is not None:
            query = query.where(MemoryEntry.role == role)

        result = await self.session.exec(query)
        entries = result.all()

        # Reverse to chronological order
        entries.reverse()

        return [
            MemorySummary(
                id=e.id,
                agent_id=e.agent_id,
                session_id=e.session_id,
                role=e.role,
                content_preview=e.content[:200],
                sequence_number=e.sequence_number,
                created_at=e.created_at,
            )
            for e in entries
        ]

    async def delete_session(
        self,
        agent_id: str,
        session_id: str,
    ) -> int:
        """Delete all memory for a specific session. Returns count deleted."""
        from sqlmodel import delete

        stmt = delete(MemoryEntry).where(
            MemoryEntry.agent_id == agent_id,
            MemoryEntry.session_id == session_id,
        )
        result = await self.session.exec(stmt)
        await self.session.commit()
        count = result.rowcount
        logger.info(
            "Session deleted: agent=%s session=%s count=%d",
            agent_id,
            session_id,
            count,
        )
        return count

    async def delete_agent_memory(
        self,
        agent_id: str,
    ) -> int:
        """Delete all memory for an agent. Returns count deleted."""
        from sqlmodel import delete

        stmt = delete(MemoryEntry).where(MemoryEntry.agent_id == agent_id)
        result = await self.session.exec(stmt)
        await self.session.commit()
        count = result.rowcount
        logger.info("Agent memory deleted: agent=%s count=%d", agent_id, count)
        return count
