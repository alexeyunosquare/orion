from temporalio.activity import defn

from orion.tools.registry import mcp_server


@defn
async def search_activity(query: str, max_results: int = 5) -> dict:
    """Temporal activity that wraps the web_search tool."""
    from fastmcp import Client  # noqa: PLC0415

    async with Client(mcp_server) as client:
        result = await client.call_tool("web_search", {"query": query, "max_results": max_results})
        return result.data if hasattr(result, "data") else {"results": []}


@defn
async def summarize_activity(text: str, model: str = "gpt-4") -> dict:
    """Temporal activity that wraps the llm_completion tool."""
    from fastmcp import Client  # noqa: PLC0415

    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "llm_completion",
            {"prompt": f"Summarize the following:\n\n{text}", "model": model},
        )
        return result.data if hasattr(result, "data") else {"output": ""}


@defn
async def report_activity(title: str, content: str, fmt: str = "markdown") -> dict:
    """Temporal activity that generates a report."""
    return {
        "title": title,
        "content": content,
        "format": fmt,
    }
