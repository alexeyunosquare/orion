"""Tests for API key authentication."""

from unittest.mock import MagicMock, patch

import pytest

from orion.security.auth import is_path_exempt, verify_api_key


class TestIsPathExempt:
    def test_health_exempt(self):
        assert is_path_exempt("/health") is True

    def test_mcp_exempt(self):
        assert is_path_exempt("/mcp/stdio") is True

    def test_docs_exempt(self):
        assert is_path_exempt("/docs") is True
        assert is_path_exempt("/redoc") is True
        assert is_path_exempt("/openapi.json") is True

    def test_api_not_exempt(self):
        assert is_path_exempt("/api/v1/tools/list") is False
        assert is_path_exempt("/api/v1/workflows/start") is False


class TestVerifyApiKey:
    @pytest.mark.asyncio
    async def test_exempt_path_skips_auth(self):
        """Exempt paths return 'exempt' regardless of API key."""
        request = MagicMock()
        request.url.path = "/health"
        result = await verify_api_key(request, None)
        assert result == "exempt"

    @pytest.mark.asyncio
    async def test_no_api_key_configured_dev_mode(self):
        """When no API key is set, any request passes (dev mode)."""
        request = MagicMock()
        request.url.path = "/api/v1/tools/list"
        result = await verify_api_key(request, None)
        assert result == "dev"

    @pytest.mark.asyncio
    async def test_valid_api_key(self):
        """Correct API key passes authentication."""
        request = MagicMock()
        request.url.path = "/api/v1/tools/list"

        with patch("orion.security.auth.settings") as mock_settings:
            mock_settings.api_key = "test-secret-key"
            mock_settings.auth_exempt_paths = ["/health"]
            result = await verify_api_key(request, "test-secret-key")
            assert result == "test-secret-key"

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_401(self):
        """Wrong API key raises 401."""
        request = MagicMock()
        request.url.path = "/api/v1/tools/list"

        with patch("orion.security.auth.settings") as mock_settings:
            mock_settings.api_key = "correct-key"
            mock_settings.auth_exempt_paths = ["/health"]

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(request, "wrong-key")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_401(self):
        """Missing API key when one is configured raises 401."""
        request = MagicMock()
        request.url.path = "/api/v1/tools/list"

        with patch("orion.security.auth.settings") as mock_settings:
            mock_settings.api_key = "correct-key"
            mock_settings.auth_exempt_paths = ["/health"]

            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(request, None)
            assert exc_info.value.status_code == 401
