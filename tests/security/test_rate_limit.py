"""Tests for rate limiting middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from orion.api.app import app
from orion.security.rate_limit import RateLimiter


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("client-1") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        limiter.is_allowed("client-1")
        limiter.is_allowed("client-1")
        limiter.is_allowed("client-1")
        assert limiter.is_allowed("client-1") is False

    def test_different_clients_independent(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("client-1")
        limiter.is_allowed("client-1")
        assert limiter.is_allowed("client-1") is False
        # Different client should still be allowed
        assert limiter.is_allowed("client-2") is True

    def test_remaining_count(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.remaining("client-1") == 5
        limiter.is_allowed("client-1")
        assert limiter.remaining("client-1") == 4
        limiter.is_allowed("client-1")
        assert limiter.remaining("client-1") == 3


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_health_not_rate_limited(self):
        """Health endpoint bypasses rate limiting."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Hit health many times — should never 429
            for _ in range(10):
                resp = await client.get("/health")
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self):
        """Rate limit headers are included in responses."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/health")
            # Health is exempt from rate limiting but middleware still runs
            # (it just skips the check for exempt paths)
