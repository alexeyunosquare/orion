from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class StreamEventType(StrEnum):
    CHUNK = "chunk"
    PROGRESS = "progress"
    ERROR = "error"
    DONE = "done"


class StreamEvent(BaseModel):
    """Standardized event emitted during streaming execution."""

    model_config = ConfigDict(use_enum_values=True)

    type: StreamEventType
    data: Any = None
    message: str | None = None
    metadata: dict[str, Any] | None = None

    def to_sse(self, event_id: int | None = None) -> str:
        """Serialize to SSE format."""
        lines = []
        if event_id is not None:
            lines.append(f"id: {event_id}")
        lines.append(f"event: {self.type}")
        lines.append(f"data: {self.model_dump_json()}")
        return "\n".join(lines) + "\n\n"
