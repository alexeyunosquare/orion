"""Tests for audit logging middleware."""

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from orion.api.app import app


class TestAuditMiddleware:
    @pytest.mark.asyncio
    async def test_audit_logger_exists(self):
        """Audit logger is configured."""
        logger = logging.getLogger("orion.audit")
        assert logger is not None

    @pytest.mark.asyncio
    async def test_health_request_logged(self, caplog):
        """Health check request triggers audit log."""
        caplog.set_level(logging.INFO, logger="orion.audit")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200

            # Check audit log was written
            audit_records = [r for r in caplog.records if r.name == "orion.audit"]
            assert len(audit_records) >= 1
            record = audit_records[0]
            assert "GET" in record.getMessage()
            assert "/health" in record.getMessage()
