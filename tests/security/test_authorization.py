"""Tests for per-tool authorization."""

import pytest

from orion.security.authorization import (
    check_tool_access,
    register_tool_permission,
    remove_tool_permission,
    reset_permissions,
)


@pytest.fixture(autouse=True)
def _clean_permissions():
    """Reset permissions before and after each test."""
    reset_permissions()
    yield
    reset_permissions()


class TestToolAuthorization:
    def test_no_restrictions_grants_access(self):
        """An unknown API key has full access."""
        assert check_tool_access("unknown-key", "web_search") is True

    def test_empty_set_grants_full_access(self):
        """Empty allowed set means no restrictions."""
        register_tool_permission("full-access-key", set())
        assert check_tool_access("full-access-key", "web_search") is True
        assert check_tool_access("full-access-key", "llm_completion") is True

    def test_restricted_key_allows_authorized_tool(self):
        """A restricted key can access allowed tools."""
        register_tool_permission("limited-key", {"web_search"})
        assert check_tool_access("limited-key", "web_search") is True
        assert check_tool_access("limited-key", "llm_completion") is False

    def test_multiple_tools_restriction(self):
        """A key with multiple allowed tools."""
        register_tool_permission("multi-key", {"web_search", "streaming_llm"})
        assert check_tool_access("multi-key", "web_search") is True
        assert check_tool_access("multi-key", "streaming_llm") is True
        assert check_tool_access("multi-key", "llm_completion") is False

    def test_remove_permission_restores_access(self):
        """Removing a permission restores full access."""
        register_tool_permission("limited-key", {"web_search"})
        # Warm the cache
        assert check_tool_access("limited-key", "llm_completion") is False
        remove_tool_permission("limited-key")
        assert check_tool_access("limited-key", "llm_completion") is True

    def test_reset_clears_all(self):
        """Reset clears all permissions."""
        register_tool_permission("key1", {"web_search"})
        register_tool_permission("key2", {"llm_completion"})
        # Warm the cache
        check_tool_access("key1", "llm_completion")
        check_tool_access("key2", "web_search")
        reset_permissions()
        assert check_tool_access("key1", "llm_completion") is True
        assert check_tool_access("key2", "web_search") is True

    def test_lru_cache_works(self):
        """The LRU cache returns consistent results."""
        register_tool_permission("cached-key", {"web_search"})
        # First call (cache miss)
        result1 = check_tool_access("cached-key", "web_search")
        # Second call (cache hit)
        result2 = check_tool_access("cached-key", "web_search")
        assert result1 is True
        assert result2 is True
