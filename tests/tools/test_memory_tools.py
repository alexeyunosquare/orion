"""Tests for memory MCP tools registration."""

import pytest

from orion.tools.registry import mcp_server


@pytest.mark.asyncio
async def test_memory_tools_registered():
    """Memory tools are registered in the MCP server."""
    tools = await mcp_server.list_tools()
    tool_names = [t.name for t in tools]
    assert "agent_memory_add" in tool_names
    assert "agent_memory_recall" in tool_names


@pytest.mark.asyncio
async def test_all_tools_registered():
    """All expected tools are registered."""
    tools = await mcp_server.list_tools()
    tool_names = [t.name for t in tools]
    assert "llm_completion" in tool_names
    assert "web_search" in tool_names
    assert "streaming_llm" in tool_names
