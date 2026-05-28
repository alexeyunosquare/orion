"""Tests for StreamEvent model."""

import pytest

from orion.streaming.events import StreamEvent, StreamEventType
from orion.tools.streaming_llm import streaming_llm


def test_stream_event_chunk() -> None:
    event = StreamEvent(
        type=StreamEventType.CHUNK,
        data={"token": "hello"},
        metadata={"position": 1},
    )
    assert event.type == "chunk"  # Enum serialized as string
    assert event.data == {"token": "hello"}


def test_stream_event_progress() -> None:
    event = StreamEvent(
        type=StreamEventType.PROGRESS,
        message="Step 2 of 5",
        metadata={"step": 2, "total": 5},
    )
    assert event.type == "progress"
    assert event.message == "Step 2 of 5"


def test_stream_event_error() -> None:
    event = StreamEvent(
        type=StreamEventType.ERROR,
        message="Rate limit exceeded",
        metadata={"retry_after": 60},
    )
    assert event.type == "error"


def test_stream_event_done() -> None:
    event = StreamEvent(
        type=StreamEventType.DONE,
        data={"summary": "Complete"},
        metadata={"duration_ms": 1234},
    )
    assert event.type == "done"


def test_stream_event_to_sse() -> None:
    event = StreamEvent(type=StreamEventType.CHUNK, data={"token": "hi"})
    sse = event.to_sse(event_id=1)
    assert "id: 1" in sse
    assert "event: chunk" in sse
    assert "data:" in sse
    assert sse.endswith("\n\n")


@pytest.mark.asyncio
async def test_streaming_llm_tool_yields_events() -> None:
    events = [event async for event in streaming_llm(prompt="hello world")]
    assert len(events) >= 3  # At least 2 chunks + progress + done

    types = [e.type for e in events]
    assert "chunk" in types
    assert "done" in types
