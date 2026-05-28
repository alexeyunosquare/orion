"""Tests for StreamManager."""

import asyncio

import pytest

from orion.streaming.manager import StreamManager


@pytest.mark.asyncio
async def test_stream_manager_register_unregister() -> None:
    manager = StreamManager()
    manager.register("test-stream")
    assert manager.active_count == 1
    manager.unregister("test-stream")
    assert manager.active_count == 0


@pytest.mark.asyncio
async def test_stream_manager_cancel_sends_sentinel() -> None:
    manager = StreamManager()
    queue = manager.register("test-stream")
    manager.cancel("test-stream")

    # Should receive sentinel (None)
    result = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert result is None


@pytest.mark.asyncio
async def test_stream_manager_cancel_already_unregistered() -> None:
    manager = StreamManager()
    manager.unregister("nonexistent")  # Should not raise
    manager.cancel("nonexistent")  # Should not raise
