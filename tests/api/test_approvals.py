"""Tests for approval API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from orion.api.app import app


def _make_mock_client(awaiting_approval: bool = True):
    """Build a mock Temporal client with proper sync/async methods.

    get_workflow_handle() is synchronous on the real client.
    handle.describe(), handle.query(), handle.signal() are async.
    """
    client = MagicMock()
    handle = MagicMock()
    handle.describe = AsyncMock(return_value={})
    handle.query = AsyncMock(
        return_value={
            "pending_approval": awaiting_approval,
            "status": "awaiting_approval" if awaiting_approval else "completed",
        }
    )
    handle.signal = AsyncMock()
    client.get_workflow_handle.return_value = handle
    return client


@pytest.mark.asyncio
async def test_approve_endpoint_exists():
    """Approval approve endpoint is registered and signals Temporal."""
    mock_client = _make_mock_client(awaiting_approval=True)

    async def mock_get_client():
        return mock_client

    with patch("orion.api.routes.approvals.get_temporal_client", side_effect=mock_get_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/approvals/test-wf/approve",
                json={"approved_by": "admin", "reason": "ok"},
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["workflow_id"] == "test-wf"
            assert data["status"] == "approved"
            mock_client.get_workflow_handle.assert_called_once_with("test-wf")
            mock_client.get_workflow_handle().signal.assert_called_once()


@pytest.mark.asyncio
async def test_approve_endpoint_rejects_non_waiting_workflow():
    """Approve returns 400 when workflow is not awaiting approval."""
    mock_client = _make_mock_client(awaiting_approval=False)

    async def mock_get_client():
        return mock_client

    with patch("orion.api.routes.approvals.get_temporal_client", side_effect=mock_get_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/approvals/test-wf/approve",
                json={"approved_by": "admin", "reason": "ok"},
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reject_endpoint_exists():
    """Approval reject endpoint is registered and signals Temporal."""
    mock_client = _make_mock_client(awaiting_approval=True)

    async def mock_get_client():
        return mock_client

    with patch("orion.api.routes.approvals.get_temporal_client", side_effect=mock_get_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/approvals/test-wf/reject",
                json={"approved_by": "admin", "reason": "no"},
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["workflow_id"] == "test-wf"
            assert data["status"] == "rejected"


@pytest.mark.asyncio
async def test_reject_endpoint_rejects_non_waiting_workflow():
    """Reject returns 400 when workflow is not awaiting approval."""
    mock_client = _make_mock_client(awaiting_approval=False)

    async def mock_get_client():
        return mock_client

    with patch("orion.api.routes.approvals.get_temporal_client", side_effect=mock_get_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/approvals/test-wf/reject",
                json={"approved_by": "admin", "reason": "no"},
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 400


@pytest.mark.asyncio
async def test_pending_approvals_endpoint_exists():
    """Pending approvals endpoint is registered."""
    mock_client = MagicMock()

    async def mock_get_client():
        return mock_client

    with patch("orion.api.routes.approvals.get_temporal_client", side_effect=mock_get_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/approvals/pending",
                headers={"X-API-Key": "test-key"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "approvals" in data
