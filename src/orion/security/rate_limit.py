"""Rate limiting middleware for Orion API."""

from collections import defaultdict
from collections.abc import Callable
from time import monotonic

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from orion.config import settings

# Paths that should not be rate limited
_RATE_LIMIT_EXEMPT = {"/health", "/docs", "/openapi.json", "/redoc"}


class RateLimiter:
    """Sliding window rate limiter.

    Tracks request timestamps per client IP and prunes old entries on each check.
    In production, replace with Redis-based rate limiting.
    """

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self.max_requests = max_requests or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Check if a client is within the rate limit window.

        Returns True if the request is allowed, False if rate limited.
        """
        now = monotonic()
        cutoff = now - self.window_seconds

        # Prune old entries
        timestamps = self._requests[client_id]
        self._requests[client_id] = [t for t in timestamps if t > cutoff]

        if len(self._requests[client_id]) >= self.max_requests:
            return False

        self._requests[client_id].append(now)
        return True

    def remaining(self, client_id: str) -> int:
        """Return remaining requests for a client in the current window."""
        now = monotonic()
        cutoff = now - self.window_seconds
        timestamps = self._requests[client_id]
        active = [t for t in timestamps if t > cutoff]
        return max(0, self.max_requests - len(active))


# Global singleton
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces per-IP rate limits."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in _RATE_LIMIT_EXEMPT:
            return await call_next(request)

        client_id = request.client.host if request.client else "unknown"

        if not rate_limiter.is_allowed(client_id):
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(rate_limiter.window_seconds),
                    "X-RateLimit-Limit": str(rate_limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(rate_limiter.remaining(client_id))
        return response
