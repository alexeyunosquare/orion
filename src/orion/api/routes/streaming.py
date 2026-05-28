"""SSE streaming endpoint for tool execution."""

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import EventSourceResponse
from pydantic import BaseModel

from orion.streaming.events import StreamEvent, StreamEventType
from orion.streaming.manager import stream_manager
from orion.tools.registry import mcp_server

router = APIRouter(prefix="/api/v1/stream", tags=["streaming"])


class StreamToolRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}


async def stream_tool_events(request: StreamToolRequest) -> AsyncIterator[str]:
    """Generator that yields SSE-formatted events from tool execution."""
    stream_id = f"{request.tool_name}:{id(request)}"
    queue = stream_manager.register(stream_id)
    event_id = 0

    start_time = time.monotonic()

    async def execute_and_queue() -> None:
        nonlocal event_id
        try:
            # For streaming tools, call the function directly
            if request.tool_name.startswith("streaming_"):
                await _execute_streaming_tool(request.tool_name, request.arguments, queue)
                return

            # Non-streaming tools: call via MCP client
            from fastmcp import Client  # noqa: PLC0415

            async with Client(mcp_server) as client:
                result = await client.call_tool(request.tool_name, request.arguments)

                content = result.content
                if not content:
                    event_id += 1
                    done_event = StreamEvent(
                        type=StreamEventType.DONE,
                        data=result.data,
                        metadata={"duration_ms": int((time.monotonic() - start_time) * 1000)},
                    )
                    await queue.put(done_event)
                    await queue.put(None)
                    return

                # Non-streaming result — wrap in single event
                event_id += 1
                chunk_event = StreamEvent(
                    type=StreamEventType.CHUNK,
                    data=_extract_data(result),
                )
                await queue.put(chunk_event)

                event_id += 1
                done_event = StreamEvent(
                    type=StreamEventType.DONE,
                    data=result.data,
                    metadata={"duration_ms": int((time.monotonic() - start_time) * 1000)},
                )
                await queue.put(done_event)

        except Exception as e:  # noqa: BLE001
            event_id += 1
            error_event = StreamEvent(
                type=StreamEventType.ERROR,
                message=str(e),
            )
            await queue.put(error_event)

        finally:
            await queue.put(None)  # Sentinel
            stream_manager.unregister(stream_id)

    # Start execution in background task
    task = asyncio.create_task(execute_and_queue())

    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            if event is None:
                break
            yield event.to_sse(event_id=event_id)
    except TimeoutError:
        yield StreamEvent(
            type=StreamEventType.ERROR,
            message="Stream timed out",
        ).to_sse()
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def _execute_streaming_tool(
    tool_name: str,
    arguments: dict[str, Any],
    queue: asyncio.Queue,
) -> None:
    """Execute a streaming tool directly to get the async iterator."""
    from orion.tools import streaming_llm as streaming_module  # noqa: PLC0415

    tool_functions = {
        "streaming_llm": streaming_module.streaming_llm,
    }

    func = tool_functions.get(tool_name)
    if func is None:
        error_event = StreamEvent(
            type=StreamEventType.ERROR,
            message=f"Streaming tool '{tool_name}' not found",
        )
        await queue.put(error_event)
        return

    try:
        async_iterator = func(**arguments)
        async for event in async_iterator:
            if isinstance(event, StreamEvent):
                await queue.put(event)
            else:
                await queue.put(StreamEvent(type=StreamEventType.CHUNK, data=event))
    except Exception as e:  # noqa: BLE001
        await queue.put(StreamEvent(type=StreamEventType.ERROR, message=str(e)))


def _extract_data(result: Any) -> Any:  # noqa: ANN401
    """Extract usable data from a CallToolResult."""
    if hasattr(result, "data") and result.data is not None:
        return result.data
    if hasattr(result, "content"):
        return [
            block.model_dump() if hasattr(block, "model_dump") else str(block)
            for block in result.content
        ]
    return result


@router.post("/invoke")
async def stream_invoke(request: StreamToolRequest) -> EventSourceResponse:
    """Stream tool execution results as SSE."""
    return EventSourceResponse(
        stream_tool_events(request),
        media_type="text/event-stream",
    )


@router.post("/cancel")
async def stream_cancel(stream_id: str) -> dict[str, str]:
    """Cancel an active streaming connection."""
    stream_manager.cancel(stream_id)
    return {"status": "cancelled", "stream_id": stream_id}
