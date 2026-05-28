"""Manage active streaming connections for cancellation."""

import asyncio
import contextlib

from orion.streaming.events import StreamEvent


class StreamManager:
    """Track active SSE streams and allow cancellation."""

    def __init__(self) -> None:
        self._active_streams: dict[str, asyncio.Queue[StreamEvent | None]] = {}
        self._cancelled: set[str] = set()

    def register(self, stream_id: str) -> asyncio.Queue[StreamEvent | None]:
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue(maxsize=100)
        self._active_streams[stream_id] = queue
        return queue

    def unregister(self, stream_id: str) -> None:
        self._active_streams.pop(stream_id, None)
        self._cancelled.discard(stream_id)

    def cancel(self, stream_id: str) -> None:
        self._cancelled.add(stream_id)
        queue = self._active_streams.get(stream_id)
        if queue is not None:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(None)  # Sentinel to close stream

    @property
    def active_count(self) -> int:
        return len(self._active_streams)


# Global singleton
stream_manager = StreamManager()
