"""Tests for WebSocket streaming endpoint."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from orion.api.app import app
from orion.streaming.events import StreamEvent, StreamEventType
from orion.streaming.redis_pubsub import redis_bridge


@pytest.fixture(autouse=True)
def mock_redis_bridge():
    """Replace the global redis_bridge with a mock for WebSocket tests."""
    mock_bridge = MagicMock(spec=redis_bridge.__class__)
    mock_bridge.subscribe = AsyncMock()
    mock_bridge.publish = AsyncMock()
    mock_bridge.channel_for_workflow = redis_bridge.channel_for_workflow

    mock_task = MagicMock()
    mock_bridge.subscribe.return_value = mock_task

    from orion.api import websocket as ws_module

    original = ws_module.redis_bridge
    ws_module.redis_bridge = mock_bridge
    yield mock_bridge
    ws_module.redis_bridge = original


@pytest.mark.asyncio
async def test_websocket_connect_and_receive(mock_redis_bridge) -> None:
    """Client connects, receives a published event, then disconnects."""
    workflow_id = "test-ws-wf-1"

    event = StreamEvent(type=StreamEventType.CHUNK, data={"token": "hello"})

    async def mock_subscribe(channel_name: str, callback):
        await callback(event.model_dump_json())
        return asyncio.create_task(asyncio.sleep(10))

    mock_redis_bridge.subscribe = mock_subscribe

    received_events: list[dict] = []

    with TestClient(app) as client, client.websocket_connect(f"/ws/stream/{workflow_id}") as ws:
        data = json.loads(ws.receive_text())
        received_events.append(data)

    assert len(received_events) == 1
    assert received_events[0]["type"] == "chunk"
    assert received_events[0]["data"] == {"token": "hello"}


@pytest.mark.asyncio
async def test_websocket_cancel_action(mock_redis_bridge) -> None:
    """Client can send a cancel action."""
    workflow_id = "test-ws-cancel-1"

    async def mock_subscribe(channel_name: str, callback):
        return asyncio.create_task(asyncio.sleep(10))

    mock_redis_bridge.subscribe = mock_subscribe

    with TestClient(app) as client, client.websocket_connect(f"/ws/stream/{workflow_id}") as ws:
        ws.send_json({"action": "cancel"})

    assert mock_redis_bridge.publish.called
    call_args = mock_redis_bridge.publish.call_args[0]
    assert "test-ws-cancel-1" in call_args[0]


@pytest.mark.asyncio
async def test_websocket_disconnect_cleans_up(mock_redis_bridge) -> None:
    """Disconnecting the client cancels the subscription task."""
    workflow_id = "test-ws-disconnect-1"

    async def mock_subscribe(channel_name: str, callback):
        return asyncio.create_task(asyncio.sleep(10))

    mock_redis_bridge.subscribe = mock_subscribe

    with TestClient(app) as client, client.websocket_connect(f"/ws/stream/{workflow_id}"):
        pass
