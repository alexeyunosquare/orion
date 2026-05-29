"""API endpoints for agent memory management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from orion.db.session import get_db
from orion.memory.models import MemoryRole
from orion.memory.service import MemoryService
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class MemoryAddRequest(BaseModel):
    agent_id: str
    content: str
    session_id: str | None = None
    role: MemoryRole = MemoryRole.USER
    metadata: dict[str, Any] | None = None


class MemoryAddResponse(BaseModel):
    id: int
    agent_id: str
    session_id: str | None
    role: MemoryRole
    sequence_number: int


class MemoryListResponse(BaseModel):
    entries: list[dict[str, Any]]
    count: int


@router.post("/add", response_model=MemoryAddResponse)
async def add_memory(
    request: MemoryAddRequest,
    db: AsyncSession = Depends(get_db),
) -> MemoryAddResponse:
    """Add a memory entry."""
    service = MemoryService(db)
    entry = await service.add(
        agent_id=request.agent_id,
        content=request.content,
        session_id=request.session_id,
        role=request.role,
        metadata=request.metadata,
    )
    return MemoryAddResponse(
        id=entry.id,
        agent_id=entry.agent_id,
        session_id=entry.session_id,
        role=entry.role,
        sequence_number=entry.sequence_number,
    )


@router.get("/{agent_id}/context", response_model=MemoryListResponse)
async def get_memory_context(
    agent_id: str,
    session_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> MemoryListResponse:
    """Get recent memory context for an agent."""
    service = MemoryService(db)
    entries = await service.get_context(
        agent_id=agent_id,
        session_id=session_id,
        limit=limit,
    )
    return MemoryListResponse(
        entries=[
            {
                "role": e.role,
                "content_preview": e.content_preview,
                "sequence": e.sequence_number,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        count=len(entries),
    )


@router.delete("/{agent_id}/sessions/{session_id}")
async def delete_session_memory(
    agent_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Delete all memory for a session."""
    service = MemoryService(db)
    count = await service.delete_session(agent_id, session_id)
    return {"deleted": count}
