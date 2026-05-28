"""Streaming LLM tool that yields events as tokens arrive."""

from collections.abc import AsyncIterator

from orion.streaming.events import StreamEvent, StreamEventType
from orion.tools.registry import mcp_server


@mcp_server.tool(
    name="streaming_llm",
    description="Get streaming LLM completion with real-time token output",
)
async def streaming_llm(
    prompt: str,
    model: str = "gpt-4",
    max_tokens: int = 100,
) -> AsyncIterator[StreamEvent]:
    """Stream LLM tokens as they arrive."""
    # Placeholder: simulate token-by-token output
    # Real implementation would use an async HTTP stream to the LLM provider
    tokens = prompt.split()
    token_count = 0

    for token in tokens:
        token_count += 1
        yield StreamEvent(
            type=StreamEventType.CHUNK,
            data={"token": token},
            metadata={"position": token_count, "model": model},
        )

    yield StreamEvent(
        type=StreamEventType.PROGRESS,
        message=f"Generated {token_count} tokens",
        metadata={"tokens": token_count, "model": model},
    )

    yield StreamEvent(
        type=StreamEventType.DONE,
        data={"total_tokens": token_count, "model": model},
        metadata={"duration_ms": 0},
    )
