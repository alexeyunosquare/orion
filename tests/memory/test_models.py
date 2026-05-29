"""Tests for memory models."""

import pytest

from orion.memory.models import MemoryEntry, MemoryRole, MemorySummary


def test_memory_entry_fields():
    entry = MemoryEntry(
        agent_id="agent-1",
        session_id="session-1",
        role=MemoryRole.USER,
        content="Hello, remember this",
        sequence_number=1,
    )
    assert entry.agent_id == "agent-1"
    assert entry.role == MemoryRole.USER
    assert entry.sequence_number == 1


def test_memory_role_enum():
    assert MemoryRole.USER == "user"
    assert MemoryRole.ASSISTANT == "assistant"
    assert MemoryRole.SYSTEM == "system"
    assert MemoryRole.TOOL == "tool"


def test_memory_entry_default_role():
    entry = MemoryEntry(
        agent_id="agent-1",
        content="test",
        sequence_number=0,
    )
    assert entry.role == MemoryRole.USER
    assert entry.session_id is None


def test_memory_entry_with_metadata():
    entry = MemoryEntry(
        agent_id="agent-1",
        content="test",
        sequence_number=0,
        meta_data={"source": "chat"},
    )
    assert entry.meta_data == {"source": "chat"}


def test_memory_summary_fields():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    summary = MemorySummary(
        id=1,
        agent_id="agent-1",
        session_id="session-1",
        role=MemoryRole.USER,
        content_preview="preview text",
        sequence_number=1,
        created_at=now,
    )
    assert summary.id == 1
    assert summary.content_preview == "preview text"
    assert summary.sequence_number == 1
