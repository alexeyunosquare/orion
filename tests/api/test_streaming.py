"""Tests for streaming SSE endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from orion.api.app import app


@pytest.mark.asyncio
async def test_stream_invoke_returns_sse() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10) as client:
        resp = await client.post(
            "/api/v1/stream/invoke",
            json={"tool_name": "streaming_llm", "arguments": {"prompt": "hi there"}},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_stream_invoke_contains_events() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10) as client:
        resp = await client.post(
            "/api/v1/stream/invoke",
            json={"tool_name": "streaming_llm", "arguments": {"prompt": "hello world"}},
        )
        assert resp.status_code == 200
        content = resp.text

        # Should contain chunk and done events
        assert '"chunk"' in content
        assert '"done"' in content


@pytest.mark.asyncio
async def test_stream_invoke_non_streaming_tool() -> None:
    """Non-streaming tools should still work via the streaming endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10) as client:
        resp = await client.post(
            "/api/v1/stream/invoke",
            json={"tool_name": "web_search", "arguments": {"query": "test"}},
        )
        assert resp.status_code == 200
        content = resp.text
        assert '"chunk"' in content
        assert '"done"' in content


@pytest.mark.asyncio
async def test_stream_invoke_unknown_tool_returns_error() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10) as client:
        resp = await client.post(
            "/api/v1/stream/invoke",
            json={"tool_name": "nonexistent_tool", "arguments": {}},
        )
        assert resp.status_code == 200  # SSE always returns 200, errors come as events
        content = resp.text
        assert '"error"' in content
