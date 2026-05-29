"""Tests for memory API endpoints."""

import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from orion.api.app import app
from orion.db.session import get_db

# ── Shared temp-file SQLite engine ──────────────────────────────────────────
# Using a file so every new connection sees the same tables (unlike :memory:).

@pytest.fixture(scope="session")
def test_engine():
    """Create a temp-file SQLite engine shared across the session."""
    path = tempfile.mktemp(suffix=".db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", echo=False)
    yield engine
    Path(path).unlink(missing_ok=True)
    engine.dispose()


@pytest.fixture(scope="session")
async def _setup_tables(test_engine):
    """Create tables once at session start."""
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def _make_test_get_db(test_engine):
    """Return an async generator that yields a fresh session on the shared engine."""
    factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _get_db() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    return _get_db


@pytest.fixture
def test_db_dependency(test_engine):
    """Return the test get_db override function."""
    return _make_test_get_db(test_engine)


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_memory_endpoint(test_db_dependency, _setup_tables):
    """POST /api/v1/memory/add creates a memory entry."""
    app.dependency_overrides[get_db] = test_db_dependency
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/memory/add",
                json={
                    "agent_id": "test-agent",
                    "content": "Remember this",
                    "role": "user",
                },
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["agent_id"] == "test-agent"
            assert data["sequence_number"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_memory_endpoint_with_session(test_db_dependency, _setup_tables):
    """POST /api/v1/memory/add with session_id."""
    app.dependency_overrides[get_db] = test_db_dependency
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/memory/add",
                json={
                    "agent_id": "test-agent",
                    "content": "Remember this",
                    "session_id": "session-1",
                    "role": "user",
                },
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == "session-1"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_context_endpoint(test_db_dependency, _setup_tables):
    """GET /api/v1/memory/{agent_id}/context returns entries."""
    app.dependency_overrides[get_db] = test_db_dependency
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Add an entry first
            await client.post(
                "/api/v1/memory/add",
                json={
                    "agent_id": "test-agent",
                    "content": "First memory",
                    "role": "user",
                },
                headers={"X-API-Key": "test-key"},
            )

            resp = await client.get(
                "/api/v1/memory/test-agent/context",
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] >= 1
            assert data["entries"][0]["role"] == "user"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_context_empty(test_db_dependency, _setup_tables):
    """GET /api/v1/memory/{agent_id}/context returns empty for unknown agent."""
    app.dependency_overrides[get_db] = test_db_dependency
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/memory/unknown-agent/context",
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_session_memory_endpoint(test_db_dependency, _setup_tables):
    """DELETE /api/v1/memory/{agent_id}/sessions/{session_id} purges session."""
    app.dependency_overrides[get_db] = test_db_dependency
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Add entries
            await client.post(
                "/api/v1/memory/add",
                json={
                    "agent_id": "test-agent",
                    "content": "A",
                    "session_id": "s1",
                    "role": "user",
                },
                headers={"X-API-Key": "test-key"},
            )
            await client.post(
                "/api/v1/memory/add",
                json={
                    "agent_id": "test-agent",
                    "content": "B",
                    "session_id": "s1",
                    "role": "user",
                },
                headers={"X-API-Key": "test-key"},
            )

            resp = await client.delete(
                "/api/v1/memory/test-agent/sessions/s1",
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["deleted"] == 2
    finally:
        app.dependency_overrides.clear()
