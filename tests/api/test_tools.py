import pytest
from httpx import ASGITransport, AsyncClient

from orion.api.app import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_tools():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/tools/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)
        tool_names = {tool["name"] for tool in data["tools"]}
        assert "web_search" in tool_names
        assert "llm_completion" in tool_names


@pytest.mark.asyncio
async def test_invoke_web_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tools/invoke",
            json={"tool_name": "web_search", "arguments": {"query": "test"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_name"] == "web_search"
        assert "output" in data


@pytest.mark.asyncio
async def test_invoke_unknown_tool():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tools/invoke",
            json={"tool_name": "nonexistent", "arguments": {}},
        )
        assert resp.status_code == 400
