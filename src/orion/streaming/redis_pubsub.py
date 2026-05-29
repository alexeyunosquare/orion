"""Redis Pub/Sub bridge for streaming fanout.

Bridges Temporal/Tool execution events to WebSocket clients via Redis channels,
enabling multi-client fanout for the same workflow stream.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import redis.asyncio as aioredis

from orion.config import settings
from orion.streaming.events import StreamEvent

logger = logging.getLogger(__name__)


class RedisStreamBridge:
    """Publish stream events to Redis channels for WebSocket fanout."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis = aioredis.from_url(redis_url or settings.redis_url, decode_responses=True)
        self._pubsub_tasks: dict[str, asyncio.Task] = {}

    @property
    def redis(self) -> aioredis.Redis:
        return self._redis

    async def publish(self, channel: str, event: StreamEvent) -> None:
        """Publish a stream event to a Redis channel."""
        await self._redis.publish(channel, event.model_dump_json())
        logger.debug("Published %s to %s", event.type, channel)

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str], Awaitable[None]],
    ) -> asyncio.Task:
        """Subscribe to a Redis channel and forward messages to the callback.

        Returns the background task so the caller can cancel it on disconnect.
        """
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)

        async def _listen() -> None:
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        await callback(message["data"])
            except asyncio.CancelledError:
                pass
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.close()

        task = asyncio.create_task(_listen())
        self._pubsub_tasks[channel] = task
        return task

    def channel_for_workflow(self, workflow_id: str) -> str:
        """Build the Redis channel name for a given workflow."""
        return f"{settings.redis_stream_channel}:{workflow_id}"

    async def close(self) -> None:
        """Cancel all active subscriptions and close the Redis connection."""
        for task in self._pubsub_tasks.values():
            task.cancel()
        self._pubsub_tasks.clear()
        await self._redis.aclose()


# Singleton shared across the application
redis_bridge = RedisStreamBridge()
