from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standardized result from tool execution."""

    output: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "output": self.output,
            "metadata": self.metadata,
            "error": self.error,
        }


@dataclass
class ToolDefinition:
    """Metadata about a registered tool."""

    name: str
    description: str
    input_schema: dict
    output_schema: dict | None = None
