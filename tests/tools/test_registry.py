import pytest
from fastmcp import Client

from orion.tools.registry import mcp_server


@pytest.mark.asyncio
async def test_tools_registered():
    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        assert "web_search" in tool_names
        assert "llm_completion" in tool_names


@pytest.mark.asyncio
async def test_tool_schemas():
    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        for tool in tools:
            assert tool.name
            assert tool.description
            assert "inputSchema" in dir(tool)
