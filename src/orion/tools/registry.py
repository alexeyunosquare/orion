from collections.abc import Callable
from typing import Any, TypeVar

from fastmcp import FastMCP

# Central MCP server instance
mcp_server = FastMCP("OrionToolRegistry")

F = TypeVar("F", bound=Callable[..., Any])


def register_tool(name: str, description: str) -> Callable[[F], F]:
    """Decorator factory to register tools on the central MCP server."""

    def decorator(func: F) -> F:
        return mcp_server.tool(name=name, description=description)(func)

    return decorator
