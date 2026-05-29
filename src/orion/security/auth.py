"""API key authentication for Orion endpoints."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from orion.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def is_path_exempt(path: str) -> bool:
    """Check if the request path is exempt from authentication."""
    return any(path.startswith(exempt) for exempt in settings.auth_exempt_paths)


async def verify_api_key(
    request: Request,
    api_key: str | None = Depends(api_key_header),
) -> str:
    """Verify the API key from the request header.

    Skips authentication in dev mode (no API key configured) or for exempt paths.
    """
    # Skip auth for exempt paths
    if is_path_exempt(request.url.path):
        return "exempt"

    # Skip in dev mode when no API key is configured
    if not settings.api_key:
        return api_key or "dev"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key
