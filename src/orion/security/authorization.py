"""Per-tool authorization — map API keys to allowed tools."""

from functools import lru_cache

from pydantic import BaseModel


class ToolPermission(BaseModel):
    """Map an API key to a set of allowed tool names."""

    api_key: str
    allowed_tools: set[str]


# In-memory store: API key -> set of allowed tools.
# Empty set means full access (no restrictions).
# In production, load from database or secrets manager.
_TOOL_PERMISSIONS: dict[str, set[str]] = {}


def register_tool_permission(api_key: str, tools: set[str]) -> None:
    """Register which tools an API key can access.

    Pass an empty set to grant full access.
    """
    _TOOL_PERMISSIONS[api_key] = tools


def remove_tool_permission(api_key: str) -> None:
    """Remove tool permissions for an API key."""
    _TOOL_PERMISSIONS.pop(api_key, None)
    check_tool_access.cache_clear()


@lru_cache(maxsize=256)
def check_tool_access(api_key: str, tool_name: str) -> bool:
    """Check if an API key has access to a specific tool.

    Returns True if the key has no restrictions (empty set) or if the
    tool is in the allowed set.
    """
    allowed = _TOOL_PERMISSIONS.get(api_key)
    # No entry or empty set = full access
    if allowed is None or len(allowed) == 0:
        return True
    return tool_name in allowed


def reset_permissions() -> None:
    """Clear all permissions. Useful for testing."""
    _TOOL_PERMISSIONS.clear()
    check_tool_access.cache_clear()
