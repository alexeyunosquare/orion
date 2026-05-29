"""Tests for memory service."""

import pytest

from orion.memory.models import MemoryEntry, MemoryRole
from orion.memory.service import MemoryService


@pytest.mark.asyncio
async def test_add_memory_entry(db_session):
    service = MemoryService(db_session)
    entry = await service.add(
        agent_id="agent-1",
        content="Test memory",
        role=MemoryRole.USER,
    )
    assert entry.id is not None
    assert entry.sequence_number == 0


@pytest.mark.asyncio
async def test_add_memory_auto_increment_sequence(db_session):
    service = MemoryService(db_session)
    e1 = await service.add(agent_id="agent-1", content="First")
    e2 = await service.add(agent_id="agent-1", content="Second")
    assert e2.sequence_number == e1.sequence_number + 1


@pytest.mark.asyncio
async def test_get_context_returns_chronological(db_session):
    service = MemoryService(db_session)
    await service.add(agent_id="agent-1", content="First")
    await service.add(agent_id="agent-1", content="Second")
    await service.add(agent_id="agent-1", content="Third")

    entries = await service.get_context(agent_id="agent-1")
    assert len(entries) == 3
    # First entry should be earliest
    assert entries[0].sequence_number < entries[-1].sequence_number


@pytest.mark.asyncio
async def test_delete_session(db_session):
    service = MemoryService(db_session)
    await service.add(agent_id="agent-1", session_id="s1", content="A")
    await service.add(agent_id="agent-1", session_id="s1", content="B")
    await service.add(agent_id="agent-1", session_id="s2", content="C")

    count = await service.delete_session("agent-1", "s1")
    assert count == 2

    remaining = await service.get_context("agent-1")
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_delete_agent_memory(db_session):
    service = MemoryService(db_session)
    await service.add(agent_id="agent-1", content="A")
    await service.add(agent_id="agent-1", content="B")
    await service.add(agent_id="agent-2", content="C")

    count = await service.delete_agent_memory("agent-1")
    assert count == 2

    remaining = await service.get_context("agent-2")
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_get_context_with_session_filter(db_session):
    service = MemoryService(db_session)
    await service.add(agent_id="agent-1", session_id="s1", content="A")
    await service.add(agent_id="agent-1", session_id="s2", content="B")

    entries = await service.get_context(agent_id="agent-1", session_id="s1")
    assert len(entries) == 1
    assert entries[0].session_id == "s1"


@pytest.mark.asyncio
async def test_get_context_with_role_filter(db_session):
    service = MemoryService(db_session)
    await service.add(agent_id="agent-1", content="User msg", role=MemoryRole.USER)
    await service.add(agent_id="agent-1", content="Assistant msg", role=MemoryRole.ASSISTANT)

    entries = await service.get_context(agent_id="agent-1", role=MemoryRole.USER)
    assert len(entries) == 1
    assert entries[0].role == MemoryRole.USER


@pytest.mark.asyncio
async def test_add_memory_with_metadata(db_session):
    service = MemoryService(db_session)
    entry = await service.add(
        agent_id="agent-1",
        content="Test",
        metadata={"key": "value"},
    )
    assert entry.meta_data == {"key": "value"}
