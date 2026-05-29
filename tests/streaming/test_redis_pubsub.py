"""Tests for RedisStreamBridge pub/sub functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from orion.streaming.events import StreamEvent, StreamEventType
from orion.streaming.redis_pubsub import RedisStreamBridge


@pytest.fixture
def bridge() -> RedisStreamBridge:
    return RedisStreamBridge()


@pytest.mark.asyncio
async def test_channel_for_workflow(bridge: RedisStreamBridge) -> None:
    """Channel name is built from settings + workflow ID."""
    channel = bridge.channel_for_workflow("wf-123")
    assert "wf-123" in channel
    assert "orion:streams" in channel


@pytest.mark.asyncio
async def test_publish_sends_json_event(bridge: RedisStreamBridge) -> None:
    """Publish serializes the event to JSON and sends to Redis."""
    event = StreamEvent(type=StreamEventType.CHUNK, data={"token": "hello"})
    mock_publish = AsyncMock()
    bridge._redis.publish = mock_publish  # type: ignore[attr-defined]

    await bridge.publish("test-channel", event)

    mock_publish.assert_called_once()
    call_args = mock_publish.call_args
    assert call_args[0][0] == "test-channel"
    assert "hello" in call_args[0][1]
    assert '"type":"chunk"' in call_args[0][1]


@pytest.mark.asyncio
async def test_subscribe_returns_task(bridge: RedisStreamBridge) -> None:
    """Subscribe creates and returns a background task."""
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.listen = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    bridge._redis.pubsub = MagicMock(return_value=mock_pubsub)  # type: ignore[attr-defined]

    callback = AsyncMock()
    task = await bridge.subscribe("test-channel", callback)

    assert isinstance(task, type(asyncio.create_task(asyncio.sleep(0))))
    assert task in bridge._pubsub_tasks.values()
    task.cancel()


@pytest.mark.asyncio
async def test_close_cancels_subscriptions(bridge: RedisStreamBridge) -> None:
    """Calling close cancels all active subscription tasks."""
    bridge._pubsub_tasks["ch1"] = asyncio.create_task(asyncio.sleep(10))
    bridge._pubsub_tasks["ch2"] = asyncio.create_task(asyncio.sleep(10))

    mock_aclose = AsyncMock()
    bridge._redis.aclose = mock_aclose  # type: ignore[attr-defined]

    await bridge.close()

    assert len(bridge._pubsub_tasks) == 0
    mock_aclose.assert_called_once()
