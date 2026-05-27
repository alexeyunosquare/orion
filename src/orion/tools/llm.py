from orion.tools.base import ToolResult
from orion.tools.registry import register_tool


@register_tool(name="llm_completion", description="Get a completion from an LLM provider")
async def llm_completion(
    prompt: str,
    model: str = "gpt-4",
    max_tokens: int = 1000,
    temperature: float = 0.7,
) -> ToolResult:
    """Call an LLM provider for text completion."""
    # Placeholder — real implementation depends on chosen LLM provider
    return ToolResult(
        output={"text": "", "model": model},
        metadata={"max_tokens": max_tokens, "temperature": temperature},
    )
