from orion.tools.base import ToolResult
from orion.tools.registry import register_tool


@register_tool(name="web_search", description="Search the web for information")
async def web_search(query: str, max_results: int = 5) -> ToolResult:
    """Execute a web search and return results."""
    # Placeholder — real implementation depends on chosen search provider
    return ToolResult(
        output={"query": query, "results": []},
        metadata={"max_results": max_results},
    )
