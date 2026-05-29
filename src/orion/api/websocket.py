"""WebSocket gateway for streaming workflow events.

Clients connect to `/ws/stream/{workflow_id}` and receive JSON-encoded
`StreamEvent` objects as they are published to the corresponding Redis channel.
"""

import asyncio
import contextlib
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orion.streaming.events import StreamEvent
from orion.streaming.redis_pubsub import redis_bridge

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/stream/{workflow_id}")
async def websocket_stream(websocket: WebSocket, workflow_id: str) -> None:
    """WebSocket endpoint for streaming workflow events.

    Subscribes to the Redis channel for the given workflow and forwards events
    to the connected client. Supports client-initiated cancellation.
    """
    await websocket.accept()
    channel = redis_bridge.channel_for_workflow(workflow_id)
    logger.info("WebSocket connected: workflow=%s channel=%s", workflow_id, channel)

    subscribe_task = await redis_bridge.subscribe(channel, websocket.send_text)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "cancel":
                logger.info("Cancel requested via WebSocket: workflow=%s", workflow_id)
                # Publish a cancellation signal so the workflow/activity layer can pick it up
                cancel_event = StreamEvent(
                    type="error",
                    message="Client requested cancellation",
                    metadata={"workflow_id": workflow_id},
                )
                await redis_bridge.publish(channel, cancel_event.model_dump())
                break
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: workflow=%s", workflow_id)
    except asyncio.CancelledError:
        pass
    finally:
        subscribe_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await subscribe_task
        await websocket.close()
        logger.info("WebSocket closed: workflow=%s", workflow_id)
