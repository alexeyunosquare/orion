"""Memory tool for agent self-referential context retrieval."""

from __future__ import annotations

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from orion.memory.models import MemoryRole
from orion.memory.service import MemoryService
from orion.tools.base import ToolResult
from orion.tools.registry import mcp_server


@mcp_server.tool(
    name="agent_memory_add",
    description="Add a memory entry to the agent's persistent memory",
)
async def agent_memory_add(
    agent_id: str,
    content: str,
    session_id: str = "",
    role: str = "user",
    metadata: dict[str, Any] | None = None,
) -> ToolResult:
    """Persist a memory entry for the agent."""
    from orion.db.session import async_session_factory

    async with async_session_factory() as session:
        service = MemoryService(session)
        entry_role = (
            MemoryRole(role) if role in MemoryRole.__members__ else MemoryRole.USER
        )
        entry = await service.add(
            agent_id=agent_id,
            content=content,
            session_id=session_id or None,
            role=entry_role,
            metadata=metadata,
        )
        return ToolResult(
            output={"id": entry.id, "sequence_number": entry.sequence_number},
            metadata={"agent_id": agent_id, "session_id": entry.session_id},
        )


@mcp_server.tool(
    name="agent_memory_recall",
    description="Recall recent memory entries for context",
)
async def agent_memory_recall(
    agent_id: str,
    session_id: str = "",
    limit: int = 50,
) -> ToolResult:
    """Retrieve recent memory entries."""
    from orion.db.session import async_session_factory

    async with async_session_factory() as session:
        service = MemoryService(session)
        entries = await service.get_context(
            agent_id=agent_id,
            session_id=session_id or None,
            limit=limit,
        )
        return ToolResult(
            output={
                "entries": [
                    {
                        "role": e.role,
                        "content": e.content_preview,
                        "sequence": e.sequence_number,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in entries
                ],
                "count": len(entries),
            },
            metadata={"agent_id": agent_id},
        )
