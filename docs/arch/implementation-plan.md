# Orion Agent Platform — Phased Implementation Plan

**Status:** Draft
**Based on:** `docs/prd.md`
**Target Python:** >= 3.12
**Package manager:** uv

---

## Table of Contents

1. [Project Bootstrap](#1-project-bootstrap)
2. [Phase 1 — Foundation: Tool Registry & Direct Execution](#2-phase-1--foundation-tool-registry--direct-execution)
3. [Phase 2 — Streaming Responses](#3-phase-2--streaming-responses)
4. [Phase 3 — Workflow Orchestration with Temporal](#4-phase-3--workflow-orchestration-with-temporal)
5. [Phase 4 — Persistence & Observability](#5-phase-4--persistence--observability)
6. [Phase 5 — Cancellation & Retry Policies](#6-phase-5--cancellation--retry-policies)
7. [Phase 6 — Security & Production Hardening](#7-phase-6--security--production-hardening)
8. [Phase 7 — Redis Pub/Sub Fanout & WebSocket Gateway](#8-phase-7--redis-pubsub-fanout--websocket-gateway)
9. [Phase 8 — Docker & Kubernetes Deployment](#9-phase-8--docker--kubernetes-deployment)
10. [Appendix A — Directory Structure](#appendix-a--directory-structure)
11. [Appendix B — Technology Decisions](#appendix-b--technology-decisions)
12. [Appendix C — API Contract](#appendix-c--api-contract)

---

## 1. Project Bootstrap

**Goal:** Initialize the project with modern Python tooling and establish the repo layout.

### 1.1 Initialize with uv

```bash
cd /Users/alex/work/alexismoscow/orion
uv init --package orion
uv add fastapi uvicorn pydantic pydantic-settings httpx
uv add temporalio fastmcp
uv add redis asyncpg sqlmodel alembic
uv add opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx
uv add tenacity
uv add --group dev pytest pytest-asyncio pytest-cov ruff ty
```

### 1.2 pyproject.toml configuration

```toml
[project]
name = "orion"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "httpx>=0.27",
    "temporalio>=1.7",
    "fastmcp>=2.10",
    "redis[hiredis]>=5.0",
    "asyncpg>=0.30",
    "sqlmodel>=0.0.22",
    "alembic>=1.13",
    "opentelemetry-api>=1.27",
    "opentelemetry-sdk>=1.27",
    "opentelemetry-instrumentation-fastapi>=0.48b",
    "opentelemetry-instrumentation-httpx>=0.48b",
    "tenacity>=9.0",
]

[dependency-groups]
dev = [{include-group = "lint"}, {include-group = "test"}]
lint = ["ruff", "ty"]
test = ["pytest", "pytest-asyncio", "pytest-cov"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["ALL"]
ignore = ["D", "COM812", "ISC001"]

[tool.pytest.ini_options]
addopts = ["--cov=orion", "--cov-fail-under=80", "-ra"]
asyncio_mode = "auto"

[tool.ty.environment]
python-version = "3.12"
```

### 1.3 Directory Structure (final target)

See [Appendix A](#appendix-a--directory-structure) for the full tree.

### 1.4 Configuration Layer

Create a central settings module using `pydantic-settings`:

**File:** `src/orion/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORION_", env_file=".env")

    # App
    app_name: str = "Orion Agent Platform"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Temporal
    temporal_host: str = "localhost"
    temporal_port: int = 7233
    temporal_namespace: str = "default"
    temporal_task_queue: str = "orion-task-queue"

    # PostgreSQL
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/orion"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_channel: str = "orion:streams"

    # Security
    api_key: Optional[str] = None
    jwt_secret: Optional[str] = None

    # Observability
    otel_endpoint: Optional[str] = None
    otel_service_name: str = "orion-platform"

    # Retry defaults
    default_max_retries: int = 3
    default_retry_backoff: float = 1.0
    default_retry_max_wait: int = 30

settings = Settings()
```

**Deliverables:**
- [ ] `pyproject.toml` with all dependencies
- [ ] `src/orion/__init__.py`
- [ ] `src/orion/config.py` with `Settings` class
- [ ] `.env.example` with all configurable vars
- [ ] `.gitignore` (venv, .env, coverage, __pycache__)
- [ ] `ruff` + `ty` passing on empty project
- [ ] `uv run pytest` passes (empty test suite)

---

## 2. Phase 1 — Foundation: Tool Registry & Direct Execution

**Goal:** Build the FastAPI gateway with FastMCP tool registration and direct tool invocation (User Story 3.1).

**PRD References:** §4.1 Tool Registry, §9.1 Direct Tool Invocation, §8 Technology Stack

### 2.1 FastMCP Server Setup

Create the MCP server that hosts all tools. Each tool is a Python function decorated with `@mcp.tool`.

**File:** `src/orion/tools/registry.py`

```python
from fastmcp import FastMCP
from typing import Any

# Central MCP server instance
mcp_server = FastMCP("OrionToolRegistry")

def register_tool(name: str, description: str):
    """Decorator factory to register tools on the central MCP server."""
    def decorator(func):
        return mcp_server.tool(name, description)(func)
    return decorator
```

**File:** `src/orion/tools/base.py`

```python
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

@dataclass
class ToolResult:
    """Standardized result from tool execution."""
    output: Any
    metadata: dict[str, Any] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "output": self.output,
            "metadata": self.metadata or {},
            "error": self.error,
        }

@dataclass
class ToolDefinition:
    """Metadata about a registered tool."""
    name: str
    description: str
    input_schema: dict
    output_schema: Optional[dict] = None
```
### 2.2 Example Tool Implementations

**File:** `src/orion/tools/search.py`

```python
import httpx
from typing import Optional
from orion.tools.registry import register_tool
from orion.tools.base import ToolResult

@register_tool(
    name="web_search",
    description="Search the web for information"
)
async def web_search(query: str, max_results: int = 5) -> ToolResult:
    """Execute a web search and return results."""
    # Implementation depends on chosen search provider
    ...
```

**File:** `src/orion/tools/llm.py`

```python
import httpx
from typing import Optional
from orion.tools.registry import register_tool
from orion.tools.base import ToolResult

@register_tool(
    name="llm_completion",
    description="Get a completion from an LLM provider"
)
async def llm_completion(
    prompt: str,
    model: str = "gpt-4",
    max_tokens: int = 1000,
    temperature: float = 0.7,
) -> ToolResult:
    """Call an LLM provider for text completion."""
    ...
```

**File:** `src/orion/tools/__init__.py`

```python
# Import all tool modules to trigger registration via decorators
from orion.tools import search, llm  # noqa: F401
```

### 2.3 FastAPI Application with MCP Integration

**File:** `src/orion/api/app.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from orion.config import settings
from orion.tools.registry import mcp_server

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in Phase 6
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP HTTP app for tool streaming
# FastMCP provides http_app() which returns an ASGI app
mcp_asgi = mcp_server.http_app()
app.mount("/mcp", mcp_asgi)
```

### 2.4 Direct Tool Invocation Endpoint

**File:** `src/orion/api/routes/tools.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from orion.tools.registry import mcp_server

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = {}

class ToolCallResponse(BaseModel):
    tool_name: str
    output: Any
    metadata: dict[str, Any] = {}

@router.get("/list")
async def list_tools():
    """List all registered tools with their schemas."""
    tools = mcp_server.list_tools()
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in tools
        ]
    }

@router.post("/invoke")
async def invoke_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Invoke a tool directly and return structured results."""
    try:
        result = await mcp_server.call_tool(
            request.tool_name,
            request.arguments,
        )
        return ToolCallResponse(
            tool_name=request.tool_name,
            output=result,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 2.5 Request Router

**File:** `src/orion/api/routes/router.py`

```python
from fastapi import APIRouter
from orion.api.routes import tools, workflows

main_router = APIRouter()
main_router.include_router(tools.router)
main_router.include_router(workflows.router)  # Phase 3
```

### 2.6 Health Check & Root

**File:** `src/orion/api/routes/health.py`

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

### 2.7 Entry Point

**File:** `src/orion/main.py`

```python
import uvicorn
from orion.config import settings

def main():
    uvicorn.run(
        "orion.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

if __name__ == "__main__":
    main()
```

### 2.8 Tests

**File:** `tests/api/test_tools.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from orion.api.app import app

@pytest.mark.asyncio
async def test_list_tools():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/tools/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

@pytest.mark.asyncio
async def test_invoke_unknown_tool():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/tools/invoke", json={
            "tool_name": "nonexistent",
            "arguments": {}
        })
        assert resp.status_code == 400
```

**Deliverables:**
- [ ] FastMCP server with tool registration via `@mcp.tool`
- [ ] At least 2 example tools (web_search, llm_completion)
- [ ] `GET /api/v1/tools/list` — returns tool schemas
- [ ] `POST /api/v1/tools/invoke` — executes tool, returns JSON result
- [ ] `/health` endpoint
- [ ] FastMCP mounted at `/mcp` for native MCP clients
- [ ] All tests passing with >= 80% coverage

---

## 3. Phase 2 — Streaming Responses

**Goal:** Implement real-time streaming for tool output (PRD §4.3).

**PRD References:** §4.3 Streaming, §7 Streaming Architecture, §9.1 Direct Tool Invocation

### 3.1 Stream Event Types

**File:** `src/orion/streaming/events.py`

```python
from pydantic import BaseModel
from typing import Any, Literal, Optional
from enum import Enum

class StreamEventType(str, Enum):
    CHUNK = "chunk"
    PROGRESS = "progress"
    ERROR = "error"
    DONE = "done"

class StreamEvent(BaseModel):
    """Standardized event emitted during streaming execution."""
    type: StreamEventType
    data: Optional[Any] = None
    message: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
```

### 3.2 Streaming Tool Support

Tools that produce streaming output yield `StreamEvent` objects:

**File:** `src/orion/tools/streaming_llm.py`

```python
from typing import AsyncIterator
from orion.tools.registry import mcp_server
from orion.streaming.events import StreamEvent, StreamEventType

@mcp_server.tool(
    name="streaming_llm",
    description="Get streaming LLM completion"
)
async def streaming_llm(
    prompt: str,
    model: str = "gpt-4",
) -> AsyncIterator[StreamEvent]:
    """Stream LLM tokens as they arrive."""
    # Yield chunk events for each token
    yield StreamEvent(type=StreamEventType.CHUNK, data={"token": "..."})
    # ...
    yield StreamEvent(type=StreamEventType.DONE)
```

### 3.3 SSE Streaming Endpoint

**File:** `src/orion/api/routes/streaming.py`

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, EventSourceResponse
from orion.streaming.events import StreamEvent, StreamEventType
from orion.tools.registry import mcp_server
from pydantic import BaseModel
import json

router = APIRouter(prefix="/api/v1/stream", tags=["streaming"])

class StreamToolRequest(BaseModel):
    tool_name: str
    arguments: dict = {}

async def stream_tool_events(request: StreamToolRequest):
    """Generator that yields SSE-formatted events from tool execution."""
    try:
        result = await mcp_server.call_tool(request.tool_name, request.arguments)

        # If result is an async iterator, yield each event
        if hasattr(result, "__aiter__"):
            async for event in result:
                if isinstance(event, StreamEvent):
                    yield event.model_dump_json()
                else:
                    yield StreamEvent(
                        type=StreamEventType.CHUNK, data=event
                    ).model_dump_json()
            yield StreamEvent(type=StreamEventType.DONE).model_dump_json()
        else:
            # Non-streaming result — wrap in single event
            yield StreamEvent(
                type=StreamEventType.CHUNK, data=result
            ).model_dump_json()
            yield StreamEvent(type=StreamEventType.DONE).model_dump_json()

    except Exception as e:
        yield StreamEvent(
            type=StreamEventType.ERROR, message=str(e)
        ).model_dump_json()

@router.post("/invoke")
async def stream_invoke(request: StreamToolRequest):
    """Stream tool execution results as SSE."""
    return EventSourceResponse(
        stream_tool_events(request),
        media_type="text/event-stream",
    )
```

### 3.4 Streaming Response Format

Each SSE event carries a JSON payload:

```json
{
    "type": "chunk",
    "data": {"token": "Hello"},
    "metadata": {"position": 1}
}
```

```json
{
    "type": "progress",
    "message": "Step 2 of 5: Analyzing results",
    "metadata": {"step": 2, "total": 5}
}
```

```json
{
    "type": "error",
    "message": "Rate limit exceeded",
    "metadata": {"retry_after": 60}
}
```

```json
{
    "type": "done",
    "data": {"summary": "Complete"},
    "metadata": {"duration_ms": 1234}
}
```

### 3.5 Tests

**File:** `tests/api/test_streaming.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from orion.api.app import app

@pytest.mark.asyncio
async def test_stream_invoke_returns_sse():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=10) as client:
        resp = await client.post(
            "/api/v1/stream/invoke",
            json={"tool_name": "streaming_llm", "arguments": {"prompt": "hi"}}
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
```

**Deliverables:**
- [ ] `StreamEvent` model with 4 event types (chunk, progress, error, done)
- [ ] `POST /api/v1/stream/invoke` — SSE streaming endpoint
- [ ] At least one streaming tool implementation
- [ ] Streaming startup latency < 1s (verified by test)
- [ ] Error events propagate correctly on tool failure

---

## 4. Phase 3 — Workflow Orchestration with Temporal

**Goal:** Implement durable workflow execution with Temporal (User Stories 3.2, 3.3, 3.4).

**PRD References:** §4.2 Workflow Orchestration, §9.2 Durable Workflow Execution, §10 Retry Strategy

### 4.1 Temporal Infrastructure

Run Temporal server via Docker Compose for local development:

**File:** `docker-compose.yml`

```yaml
services:
  temporal:
    image: temporalio/auto-setup:latest
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_HOST=db
      - POSTGRES_PORT=5432
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    ports:
      - "7233:7233"
      - "8233:8233"  # Web UI
    depends_on:
      - db

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: temporal
    ports:
      - "5433:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  orion-app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ORION_TEMPORAL_HOST=temporal
      - ORION_DB_URL=postgresql+asyncpg://postgres:postgres@orion-db:5432/orion
      - ORION_REDIS_URL=redis://redis:6379/0
    depends_on:
      - temporal
      - redis
      - orion-db

  orion-db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: orion
    ports:
      - "5432:5432"
```

### 4.2 Temporal Client Setup

**File:** `src/orion/workflow/client.py`

```python
from temporalio.client import Client
from orion.config import settings

_temporal_client: Client | None = None

async def get_temporal_client() -> Client:
    """Get or create the Temporal client singleton."""
    global _temporal_client
    if _temporal_client is None:
        _temporal_client = await Client.connect(
            f"{settings.temporal_host}:{settings.temporal_port}",
            namespace=settings.temporal_namespace,
        )
    return _temporal_client
```

### 4.3 Temporal Worker Setup

**File:** `src/orion/workflow/worker.py`

```python
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from orion.config import settings
from orion.workflow.activities import (
    search_activity,
    summarize_activity,
    report_activity,
)

async def start_worker(client: Client):
    """Start the Temporal worker with all activities and workflows."""
    worker = Worker(
        client=client,
        task_queue=settings.temporal_task_queue,
        activities=[search_activity, summarize_activity, report_activity],
        workflows=[],  # Workflows are auto-discovered via decorators
    )
    print(f"Worker started on task queue: {settings.temporal_task_queue}")
    await worker.run()
```

### 4.4 Activity Definitions

Activities are the executable units that call tools.

**File:** `src/orion/workflow/activities.py`

```python
from temporalio.activity import define
import httpx
from orion.tools.registry import mcp_server
from orion.retry.policy import with_retry

@define
@with_retry(max_attempts=3, backoff=1.0, max_wait=30)
async def search_activity(query: str, max_results: int = 5) -> dict:
    """Temporal activity that wraps the web_search tool."""
    result = await mcp_server.call_tool("web_search", {
        "query": query,
        "max_results": max_results,
    })
    return result

@define
@with_retry(max_attempts=3, backoff=1.0, max_wait=30)
async def summarize_activity(text: str, model: str = "gpt-4") -> dict:
    """Temporal activity that wraps the llm_completion tool."""
    result = await mcp_server.call_tool("llm_completion", {
        "prompt": f"Summarize the following:\n\n{text}",
        "model": model,
    })
    return result

@define
async def report_activity(
    title: str, content: str, format: str = "markdown"
) -> dict:
    """Temporal activity that generates a report."""
    # Generate and persist report
    ...
```

### 4.5 Workflow Definitions

**File:** `src/orion/workflow/workflows.py`

```python
from temporalio.workflow import (
    workflow,
    activity,
    retry_policy,
)
from datetime import timedelta
from typing import Any

from orion.workflow import activities

@workflow.defn(name="research_workflow")
class ResearchWorkflow:
    """Multi-step research workflow: search, summarize, report."""

    @workflow.run
    async def run(self, input: dict[str, Any]) -> dict[str, Any]:
        query = input["query"]
        model = input.get("model", "gpt-4")

        # Step 1: Search
        search_results = await activity.execute(
            activities.search_activity,
            query=query,
            max_results=input.get("max_results", 5),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy.RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
            ),
        )

        # Step 2: Summarize
        combined_text = "\n\n".join(
            r.get("text", "") for r in search_results.get("results", [])
        )
        summary = await activity.execute(
            activities.summarize_activity,
            text=combined_text,
            model=model,
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy.RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
            ),
        )

        # Step 3: Generate report
        report = await activity.execute(
            activities.report_activity,
            title=f"Research: {query}",
            content=summary.get("output", ""),
            format="markdown",
            start_to_close_timeout=timedelta(seconds=60),
        )

        return {
            "search_results": search_results,
            "summary": summary,
            "report": report,
        }
```

### 4.6 Workflow Signal & Query

**File:** `src/orion/workflow/workflows.py` (add to ResearchWorkflow)

```python
    @workflow.signal(name="cancel_request")
    async def handle_cancel(self):
        """Handle external cancellation signal."""
        workflow.logger.info("Cancellation requested via signal")
        # Set a flag that activities can check
        self._cancelled = True

    @workflow.query
    def get_progress(self) -> dict:
        """Query current workflow progress without blocking."""
        return {
            "status": self._status,
            "step": self._current_step,
            "total_steps": 3,
        }
```

### 4.7 Workflow API Endpoints

**File:** `src/orion/api/routes/workflows.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
import uuid

from orion.workflow.client import get_temporal_client
from orion.workflow import workflows

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])

class WorkflowStartRequest(BaseModel):
    workflow_type: str
    input: dict[str, Any]
    id: Optional[str] = None

class WorkflowStartResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str = "started"

class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    result: Optional[Any] = None

@router.post("/start")
async def start_workflow(request: WorkflowStartRequest) -> WorkflowStartResponse:
    """Start a new workflow execution."""
    client = await get_temporal_client()

    workflow_id = request.id or str(uuid.uuid4())
    workflow_type = request.workflow_type

    handle = await client.start_workflow(
        workflow_type,
        request.input,
        id=workflow_id,
        task_queue="orion-task-queue",
    )

    return WorkflowStartResponse(
        workflow_id=handle.id,
        run_id=handle.run_id,
        status="started",
    )

@router.get("/{workflow_id}/status")
async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """Get the current status of a workflow execution."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    description = await handle.describe()

    return WorkflowStatusResponse(
        workflow_id=workflow_id,
        run_id=description.run_id,
        status=description.status.value,
    )

@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.cancel()
    return {"workflow_id": workflow_id, "status": "cancelling"}

@router.post("/{workflow_id}/signal")
async def signal_workflow(workflow_id: str, signal_name: str, args: dict = {}):
    """Send a signal to a running workflow."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(signal_name, args)
    return {"workflow_id": workflow_id, "signal": signal_name}

@router.get("/{workflow_id}/history")
async def get_workflow_history(workflow_id: str):
    """Get the full event history of a workflow execution."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    history = await handle.fetch_history()
    return {
        "workflow_id": workflow_id,
        "events": history.history.events,
    }
```

### 4.8 Tests

**File:** `tests/workflow/test_workflows.py`

```python
import pytest
from temporalio.client import Client
from orion.workflow.workflows import ResearchWorkflow

@pytest.mark.asyncio
async def test_research_workflow_execution(temporal_client: Client):
    result = await temporal_client.execute_workflow(
        ResearchWorkflow.run,
        {"query": "Python async patterns"},
        id="test-research-1",
        task_queue="orion-task-queue",
    )
    assert "search_results" in result
    assert "summary" in result
    assert "report" in result
```

**Deliverables:**
- [ ] Temporal client singleton with connection management
- [ ] Temporal worker with activity registration
- [ ] `ResearchWorkflow` with 3 activities (search, summarize, report)
- [ ] `POST /api/v1/workflows/start` — start workflow, return ID
- [ ] `GET /api/v1/workflows/{id}/status` — query status
- [ ] `POST /api/v1/workflows/{id}/cancel` — cancel execution
- [ ] `POST /api/v1/workflows/{id}/signal` — send signal
- [ ] `GET /api/v1/workflows/{id}/history` — view event history
- [ ] docker-compose.yml with Temporal, PostgreSQL, Redis
- [ ] Workflow survives worker restart (Temporal durability guarantee)

---

## 5. Phase 4 — Persistence & Observability

**Goal:** Implement PostgreSQL persistence for execution metadata and OpenTelemetry observability.

**PRD References:** §4.4 Persistence, §5.4 Observability, §11 Persistence Model, §12 Security Requirements (audit logging)

### 5.1 Database Models

**File:** `src/orion/db/models.py`

```python
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
from enum import Enum

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ExecutionRequest(SQLModel, table=True):
    """Persisted record of each tool/workflow invocation."""
    __tablename__ = "execution_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    correlation_id: str = Field(index=True, unique=True)
    workflow_id: Optional[str] = Field(index=True)
    tool_name: Optional[str]
    input_data: dict = Field(default_factory=dict)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    activities: list["ActivityRecord"] = Relationship(back_populates="request")
    outputs: list["ExecutionOutput"] = Relationship(back_populates="request")

class ActivityRecord(SQLModel, table=True):
    """Individual activity execution within a workflow."""
    __tablename__ = "activity_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: int = Field(foreign_key="execution_requests.id")
    activity_type: str
    attempt: int = 1
    status: WorkflowStatus = WorkflowStatus.PENDING
    error: Optional[str]
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    request: Optional[ExecutionRequest] = Relationship(back_populates="activities")

class ExecutionOutput(SQLModel, table=True):
    """Final output of an execution."""
    __tablename__ = "execution_outputs"

    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: int = Field(foreign_key="execution_requests.id")
    output_data: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    request: Optional[ExecutionRequest] = Relationship(back_populates="outputs")
```

### 5.2 Database Session Management

**File:** `src/orion/db/session.py`

```python
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from orion.config import settings

engine = create_async_engine(settings.db_url, echo=settings.debug)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_db() -> AsyncSession:
    """FastAPI dependency for database sessions."""
    async with async_session_factory() as session:
        yield session
```

### 5.3 Alembic Migrations

Initialize Alembic for production migrations:

```bash
cd src/orion
uv run alembic init alembic
```

**File:** `src/orion/alembic/alembic.ini` — update `sqlalchemy.url` to use env vars.

**File:** `src/orion/alembic/env.py` — configure async environment with SQLModel.

### 5.4 OpenTelemetry Instrumentation

**File:** `src/orion/observability/tracing.py`

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXInstrumentor
from orion.config import settings

def setup_tracing():
    """Configure OpenTelemetry tracing."""
    if not settings.otel_endpoint:
        # Development: use console exporter
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        exporter = ConsoleSpanExporter()
    else:
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)

    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)  # Import app after definition

    # Instrument HTTPX (outgoing requests from tools)
    HTTPXInstrumentor().instrument()

    return trace.get_tracer(settings.otel_service_name)
```

### 5.5 Structured Logging

**File:** `src/orion/observability/logging.py`

```python
import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id
        if hasattr(record, "workflow_id"):
            log_entry["workflow_id"] = record.workflow_id
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logging(level: str = "INFO"):
    """Configure structured logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    root_logger.addHandler(handler)
```

### 5.6 Metrics Collection

Track key metrics from PRD §15:

**File:** `src/orion/observability/metrics.py`

```python
from opentelemetry import metrics
from orion.config import settings

_meter = None

def get_meter():
    global _meter
    if _meter is None:
        _meter = metrics.get_meter_provider().get_meter(settings.otel_service_name)

        # Workflow success rate
        _meter.create_counter(
            name="workflow.completed",
            description="Total completed workflows",
        )
        _meter.create_counter(
            name="workflow.failed",
            description="Total failed workflows",
        )

        # Tool latency
        _meter.create_histogram(
            name="tool.latency.ms",
            description="Tool execution latency in milliseconds",
            unit="ms",
        )

        # Streaming startup latency
        _meter.create_histogram(
            name="stream.startup.latency.ms",
            description="Streaming startup latency in milliseconds",
            unit="ms",
        )

        # Retry metrics
        _meter.create_counter(
            name="activity.retry.attempt",
            description="Activity retry attempts",
        )

        # Cancellation propagation time
        _meter.create_histogram(
            name="cancellation.propagation.ms",
            description="Time from cancel request to activity termination",
            unit="ms",
        )

    return _meter
```

### 5.7 Integration with API

Wire up database and tracing in the app lifespan:

**File:** `src/orion/api/app.py` (updated)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from orion.config import settings
from orion.db.session import init_db
from orion.observability.tracing import setup_tracing
from orion.observability.logging import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging("DEBUG" if settings.debug else "INFO")
    setup_tracing()
    await init_db()
    yield
    # Shutdown — cleanup connections

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)
```

### 5.8 Tests

**File:** `tests/db/test_models.py`

```python
import pytest
from sqlmodel import select
from orion.db.models import ExecutionRequest, WorkflowStatus

@pytest.mark.asyncio
async def test_create_execution_request(db_session):
    request = ExecutionRequest(
        correlation_id="test-001",
        tool_name="web_search",
        input_data={"query": "test"},
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)

    assert request.id is not None
    assert request.status == WorkflowStatus.PENDING
```

**Deliverables:**
- [ ] SQLModel models: `ExecutionRequest`, `ActivityRecord`, `ExecutionOutput`
- [ ] Async database session management with `asyncpg`
- [ ] Alembic migration scaffolding
- [ ] OpenTelemetry tracing (FastAPI + HTTPX instrumentation)
- [ ] Structured JSON logging with correlation IDs
- [ ] OTel metrics for all PRD §15 success metrics
- [ ] Database initialized on app startup

---

## 6. Phase 5 — Cancellation & Retry Policies

**Goal:** Implement cooperative cancellation (User Story 3.3) and comprehensive retry handling (PRD §4.5, §10).

**PRD References:** §4.5 Retry Handling, §4.6 Cancellation, §10 Retry Strategy

### 6.1 Tenacity Retry Decorator for Tools

**File:** `src/orion/retry/policy.py`

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    AsyncRetrying,
)
import logging
from typing import Callable

logger = logging.getLogger(__name__)

# Classify exceptions for retry logic
TRANSIENT_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    httpx.HTTPError,  # Rate limits, 5xx
)

NON_TRANSIENT_EXCEPTIONS = (
    ValueError,
    TypeError,
    httpx.HTTPStatusError,  # 4xx — fail fast
)

def with_retry(
    max_attempts: int = 3,
    backoff: float = 1.0,
    max_wait: int = 30,
    retryable_exceptions: tuple = TRANSIENT_EXCEPTIONS,
):
    """
    Tenacity retry decorator for tool functions.

    Used inside tools for transient HTTP failures,
    LLM provider timeouts, temporary rate limits.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )

async def retrying_execute(
    func: Callable,
    *args,
    max_attempts: int = 3,
    backoff: float = 1.0,
    max_wait: int = 30,
    **kwargs,
):
    """
    Execute an async function with Tenacity retry logic.
    Returns the result or raises RetryError after all attempts.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff, max=max_wait),
        retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    ):
        with attempt:
            return await func(*args, **kwargs)
```

### 6.2 Workflow-Level Cancellation

**File:** `src/orion/workflow/cancellation.py`

```python
from temporalio.workflow import cancellation_scope, ExternalInputFailure
from datetime import timedelta

async def cancellable_activity_execute(activity_fn, *args, timeout=timedelta(seconds=3), **kwargs):
    """
    Execute an activity within a cancellation scope.
    Propagates cancellation within the specified timeout.
    """
    with cancellation_scope(timeout=timeout) as scope:
        try:
            result = await activity_fn(*args, **kwargs)
            return result
        except Exception as e:
            if scope.cancel_requested:
                raise CancellationError(f"Activity cancelled: {activity_fn.__name__}")
            raise
```

### 6.3 Cancellation API Integration

Update the workflow cancellation endpoint to measure propagation time:

**File:** `src/orion/api/routes/workflows.py` (updated cancel)

```python
import time
from orion.observability.metrics import get_meter

@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow. Propagation target: < 3s."""
    start = time.monotonic()
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.cancel()

    # Measure cancellation propagation
    elapsed_ms = (time.monotonic() - start) * 1000
    get_meter().record_histogram(
        "cancellation.propagation.ms",
        elapsed_ms,
    )

    return {
        "workflow_id": workflow_id,
        "status": "cancelling",
        "propagation_ms": round(elapsed_ms, 2),
    }
```

### 6.4 Streaming Cancellation

Close SSE connections on cancellation:

**File:** `src/orion/streaming/manager.py`

```python
import asyncio
from typing import Dict, Set
from uuid import UUID

class StreamManager:
    """Manage active streaming connections for cancellation."""

    def __init__(self):
        self._active_streams: Dict[str, asyncio.Queue] = {}
        self._cancelled: Set[str] = set()

    def register(self, stream_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=100)
        self._active_streams[stream_id] = queue
        return queue

    def unregister(self, stream_id: str):
        self._active_streams.pop(stream_id, None)
        self._cancelled.discard(stream_id)

    def cancel(self, stream_id: str):
        self._cancelled.add(stream_id)
        # Signal the queue to close
        queue = self._active_streams.get(stream_id)
        if queue:
            try:
                queue.put_nowait(None)  # Sentinel to close stream
            except asyncio.QueueFull:
                pass

    @property
    def active_count(self) -> int:
        return len(self._active_streams)

# Global singleton
stream_manager = StreamManager()
```

### 6.5 Tests

**File:** `tests/retry/test_policy.py`

```python
import pytest
from orion.retry.policy import with_retry, TRANSIENT_EXCEPTIONS

@pytest.mark.asyncio
async def test_retry_on_transient_error():
    call_count = 0

    @with_retry(max_attempts=3, backoff=0.1)
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient")
        return "success"

    result = await flaky_func()
    assert result == "success"
    assert call_count == 3

@pytest.mark.asyncio
async def test_no_retry_on_non_transient():
    @with_retry(max_attempts=3)
    async def bad_input():
        raise ValueError("invalid")

    with pytest.raises(ValueError):
        await bad_input()
```

**Deliverables:**
- [ ] `with_retry` decorator using Tenacity (exponential backoff)
- [ ] Transient vs non-transient exception classification
- [ ] Cancellation scope wrapper for activities (< 3s propagation)
- [ ] `StreamManager` for tracking/cancelling active SSE connections
- [ ] Cancellation propagation metric
- [ ] All retry and cancellation tests passing

---

## 7. Phase 6 — Security & Production Hardening

**Goal:** Implement API key authentication, rate limiting, and production-grade security (PRD §12).

**PRD References:** §12 Security Requirements

### 6.1 API Key Authentication

**File:** `src/orion/security/auth.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from orion.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Verify the API key from the request header."""
    if not settings.api_key:
        return api_key or "dev"  # Skip in dev mode

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key
```

### 6.2 Per-Tool Authorization

**File:** `src/orion/security/authorization.py`

```python
from typing import Set
from pydantic import BaseModel

class ToolPermission(BaseModel):
    """Map API keys to allowed tools."""
    api_key: str
    allowed_tools: Set[str]

# In production, load from database or secrets manager
_TOOL_PERMISSIONS: dict[str, Set[str]] = {}

def register_tool_permission(api_key: str, tools: Set[str]):
    _TOOL_PERMISSIONS[api_key] = tools

def check_tool_access(api_key: str, tool_name: str) -> bool:
    allowed = _TOOL_PERMISSIONS.get(api_key, set())
    return not allowed or tool_name in allowed  # Empty = all access
```

### 6.3 Rate Limiting

**File:** `src/orion/security/rate_limit.py`

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
import time

class RateLimiter:
    """Simple in-memory rate limiter. Replace with Redis in production."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.monotonic()
        # Prune old requests
        self._requests[client_id] = [
            t for t in self._requests[client_id]
            if now - t < self.window_seconds
        ]
        if len(self._requests[client_id]) >= self.max_requests:
            return False
        self._requests[client_id].append(now)
        return True

rate_limiter = RateLimiter()

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_id = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return await call_next(request)
```

### 6.4 Encrypted Secrets Storage

Use environment variables + `.env` for secrets. In production, integrate with AWS Secrets Manager, HashiCorp Vault, or similar.

**File:** `src/orion/security/secrets.py`

```python
from cryptography.fernet import Fernet
from orion.config import settings

# In production, load key from a secure secrets manager
_fernet = None

def get_fernet():
    global _fernet
    if _fernet is None and settings.jwt_secret:
        # Derive Fernet key from JWT secret
        key = settings.jwt_secret.encode()
        _fernet = Fernet(key[:32].ljust(32, b'\0'))
    return _fernet

def encrypt_secret(plaintext: str) -> str:
    f = get_fernet()
    if not f:
        return plaintext  # No encryption configured
    return f.encrypt(plaintext.encode()).decode()

def decrypt_secret(ciphertext: str) -> str:
    f = get_fernet()
    if not f:
        return ciphertext
    return f.decrypt(ciphertext.encode()).decode()
```

### 6.5 CORS Hardening

**File:** `src/orion/api/app.py` (updated middleware)

```python
from orion.config import settings

# In production, restrict origins
ALLOWED_ORIGINS = getattr(settings, "allowed_origins", ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)
```

### 6.6 Audit Logging Middleware

**File:** `src/orion/security/audit.py`

```python
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone

audit_logger = logging.getLogger("orion.audit")

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = datetime.now(timezone.utc)
        response = await call_next(request)
        duration = (datetime.now(timezone.utc) - start).total_seconds()

        audit_logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"duration={duration:.3f}s "
            f"client={request.client.host}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration": duration,
            },
        )
        return response
```

### 6.7 Tests

**File:** `tests/security/test_auth.py`

```python
import pytest
from orion.security.auth import verify_api_key

@pytest.mark.asyncio
async def test_valid_api_key():
    # With ORION_API_KEY set
    result = await verify_api_key("correct-key")
    assert result == "correct-key"

@pytest.mark.asyncio
async def test_invalid_api_key():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await verify_api_key("wrong-key")
    assert exc_info.value.status_code == 401
```

**Deliverables:**
- [ ] API key authentication via `X-API-Key` header
- [ ] Per-tool authorization (API key → allowed tools mapping)
- [ ] Rate limiting middleware (configurable requests/minute)
- [ ] Encrypted secrets storage (Fernet)
- [ ] Audit logging middleware
- [ ] CORS hardening with configurable origins
- [ ] Security tests passing

---

## 8. Phase 7 — Redis Pub/Sub Fanout & WebSocket Gateway

**Goal:** Optional WebSocket fanout for multi-client streaming (PRD §7, optional path).

**PRD References:** §7 Streaming Architecture (optional fanout), §5.2 Scalability (10k concurrent sessions)

### 7.1 Redis Pub/Sub Bridge

**File:** `src/orion/streaming/redis_pubsub.py`

```python
import asyncio
import json
import redis.asyncio as aioredis
from typing import Callable, Awaitable
from orion.config import settings
from orion.streaming.events import StreamEvent

class RedisStreamBridge:
    """
    Bridge between Temporal/Tool execution and WebSocket clients.
    Publishes stream events to Redis channels for fanout.
    """

    def __init__(self, redis_url: str = None):
        self.redis = aioredis.from_url(redis_url or settings.redis_url)
        self._subscribers: dict[str, list[Callable]] = {}

    async def publish(self, channel: str, event: StreamEvent):
        """Publish a stream event to a Redis channel."""
        await self.redis.publish(channel, event.model_dump_json())

    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]):
        """Subscribe to a Redis channel."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                await callback(message["data"].decode())

    async def close(self):
        await self.redis.close()

# Singleton
redis_bridge = RedisStreamBridge()
```

### 7.2 WebSocket Gateway

**File:** `src/orion/api/websocket.py`

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from orion.streaming.redis_pubsub import redis_bridge
from orion.streaming.events import StreamEvent
import json

router = APIRouter(tags=["websocket"])

@router.websocket("/ws/stream/{workflow_id}")
async def websocket_stream(websocket: WebSocket, workflow_id: str):
    """WebSocket endpoint for streaming workflow events."""
    await websocket.accept()

    channel = f"orion:stream:{workflow_id}"

    async def on_message(data: str):
        event = StreamEvent.model_validate_json(data)
        await websocket.send_json(event.model_dump())

    # Subscribe to Redis channel for this workflow
    task = asyncio.create_task(redis_bridge.subscribe(channel, on_message))

    try:
        # Keep connection alive
        while True:
            # Handle client messages (e.g., cancel)
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("action") == "cancel":
                # Signal cancellation
                ...
    except WebSocketDisconnect:
        task.cancel()
    except asyncio.CancelledError:
        pass
    finally:
        await websocket.close()
```

### 7.3 Tests

**File:** `tests/streaming/test_redis_pubsub.py`

```python
import pytest
from orion.streaming.redis_pubsub import RedisStreamBridge
from orion.streaming.events import StreamEvent, StreamEventType

@pytest.mark.asyncio
async def test_redis_publish_subscribe():
    bridge = RedisStreamBridge()
    received = []

    async def callback(data):
        received.append(data)

    # Start subscriber
    sub_task = asyncio.create_task(bridge.subscribe("test-channel", callback))

    # Publish
    event = StreamEvent(type=StreamEventType.CHUNK, data={"token": "hello"})
    await bridge.publish("test-channel", event)

    await asyncio.sleep(0.1)  # Allow message delivery
    sub_task.cancel()

    assert len(received) > 0
    await bridge.close()
```

**Deliverables:**
- [ ] `RedisStreamBridge` for pub/sub between workers and gateway
- [ ] `WS /ws/stream/{workflow_id}` — WebSocket streaming endpoint
- [ ] Multi-client fanout for same workflow
- [ ] Graceful disconnect handling

---

## 9. Phase 8 — Docker & Kubernetes Deployment

**Goal:** Containerize the application and prepare for Kubernetes deployment (PRD §8, §5.2).

### 8.1 Dockerfile

**File:** `Dockerfile`

```dockerfile
# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install uv
RUN pip install --no-cache-dir uv
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Runtime stage
FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Run API server
CMD ["uvicorn", "orion.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8.2 Worker Dockerfile

**File:** `Dockerfile.worker`

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv
RUN uv sync --frozen --no-dev
COPY src/ src/

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "orion.workflow.worker"]
```

### 8.3 Kubernetes Manifests

**File:** `k8s/deployment-api.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orion-api
  labels:
    app: orion
    component: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orion
      component: api
  template:
    metadata:
      labels:
        app: orion
        component: api
    spec:
      containers:
        - name: api
          image: orion-api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: orion-secrets
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: orion-api
spec:
  selector:
    app: orion
    component: api
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

**File:** `k8s/deployment-worker.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orion-worker
  labels:
    app: orion
    component: worker
spec:
  replicas: 2  # Scale horizontally for activity execution
  selector:
    matchLabels:
      app: orion
      component: worker
  template:
    metadata:
      labels:
        app: orion
        component: worker
    spec:
      containers:
        - name: worker
          image: orion-worker:latest
          envFrom:
            - secretRef:
                name: orion-secrets
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
```

### 8.4 Helm Chart (future)

Create a Helm chart for parameterized deployment:

```
k8s/helm/orion/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment-api.yaml
    ├── deployment-worker.yaml
    ├── service.yaml
    ├── configmap.yaml
    └── secrets.yaml
```

### 8.5 Tests

**File:** `tests/deployment/test_docker.py`

```python
import pytest
import subprocess

@pytest.mark.integration
def test_docker_build():
    result = subprocess.run(
        ["docker", "build", "-t", "orion-api:test", "."],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

@pytest.mark.integration
def test_docker_health_check():
    result = subprocess.run(
        ["docker", "run", "--rm", "-p", "8000:8000", "orion-api:test"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Check container started and health endpoint responded
    assert "ERROR" not in result.stderr
```

**Deliverables:**
- [ ] Multi-stage Dockerfile for API
- [ ] Separate Dockerfile for Worker
- [ ] docker-compose.yml for local dev (Temporal + PostgreSQL + Redis + API + Worker)
- [ ] Kubernetes Deployment + Service manifests
- [ ] Health check probes (readiness + liveness)
- [ ] Resource limits configured
- [ ] Horizontal pod autoscaling ready

---

## Appendix A — Directory Structure

```
orion/
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── .gitignore
├── Dockerfile
├── Dockerfile.worker
├── docker-compose.yml
├── docs/
│   ├── prd.md
│   └── arch/
│       ├── implementation-plan.md    ← this file
│       ├── decisions/               ← ADRs
│       │   └── 001-tech-stack.md
│       └── diagrams/               ← architecture diagrams
├── src/
│   └── orion/
│       ├── __init__.py
│       ├── main.py                  ← uvicorn entry point
│       ├── config.py                ← pydantic-settings
│       ├──
│       │   └── (modules organized by domain)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── app.py               ← FastAPI app, lifespan, middleware
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── router.py        ← main router aggregation
│       │   │   ├── health.py        ← /health
│       │   │   ├── tools.py         ← /api/v1/tools/*
│       │   │   ├── streaming.py     ← /api/v1/stream/*
│       │   │   └── workflows.py     ← /api/v1/workflows/*
│       │   └── websocket.py         ← /ws/stream/{id}
│       ├── tools/
│       │   ├── __init__.py          ← import all tool modules
│       │   ├── base.py              ← ToolResult, ToolDefinition
│       │   ├── registry.py          ← FastMCP server, @register_tool
│       │   ├── search.py            ← web_search tool
│       │   ├── llm.py               ← llm_completion tool
│       │   └── streaming_llm.py     ← streaming LLM tool
│       ├── workflow/
│       │   ├── __init__.py
│       │   ├── client.py            ← Temporal client singleton
│       │   ├── worker.py            ← Temporal worker startup
│       │   ├── activities.py        ← @define activity functions
│       │   ├── workflows.py         ← @workflow.defn classes
│       │   └── cancellation.py      ← cancellation scope helpers
│       ├── streaming/
│       │   ├── __init__.py
│       │   ├── events.py            ← StreamEvent, StreamEventType
│       │   ├── manager.py           ← StreamManager (active connections)
│       │   └── redis_pubsub.py      ← RedisStreamBridge
│       ├── retry/
│       │   ├── __init__.py
│       │   └── policy.py            ← with_retry, retrying_execute
│       ├── db/
│       │   ├── __init__.py
│       │   ├── models.py            ← SQLModel tables
│       │   ├── session.py           ← async session factory
│       │   └── alembic/             ← migration scripts
│       ├── security/
│       │   ├── __init__.py
│       │   ├── auth.py              ← API key verification
│       │   ├── authorization.py     ← per-tool access control
│       │   ├── rate_limit.py        ← rate limiting middleware
│       │   ├── secrets.py           ← encrypted secret storage
│       │   └── audit.py             ← audit logging middleware
│       └── observability/
│           ├── __init__.py
│           ├── tracing.py           ← OpenTelemetry setup
│           ├── logging.py           ← structured JSON logging
│           └── metrics.py           ← OTel metrics definitions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  ← shared fixtures
│   ├── api/
│   │   ├── test_tools.py
│   │   ├── test_streaming.py
│   │   └── test_workflows.py
│   ├── tools/
│   │   └── test_registry.py
│   ├── workflow/
│   │   └── test_workflows.py
│   ├── db/
│   │   └── test_models.py
│   ├── retry/
│   │   └── test_policy.py
│   ├── security/
│   │   └── test_auth.py
│   ├── streaming/
│   │   └── test_redis_pubsub.py
│   └── deployment/
│       └── test_docker.py
│
├── k8s/
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   └── helm/
│       └── orion/
│           ├── Chart.yaml
│           ├── values.yaml
│           └── templates/
│
└── scripts/
    ├── start-worker.sh              ← local worker launcher
    └── migrate.sh                   ← alembic migration wrapper
```

---

## Appendix B — Technology Decisions

### B.1 Why FastAPI

- Native async support with `async def` endpoints
- Automatic OpenAPI schema generation (useful for tool discovery)
- `EventSourceResponse` for SSE streaming (PRD §4.3)
- Dependency injection for sessions, auth, clients
- Strong ecosystem (pydantic, uvicorn)
- ASGI-compatible — mounts MCP server as sub-app

### B.2 Why FastMCP

- Pythonic `@mcp.tool` decorator — tools are plain functions
- Automatic schema generation from type hints
- Built-in `http_app()` for FastAPI mounting
- Supports both sync and async tools
- `ToolResult` for full output control
- Generator-based streaming for real-time output

### B.3 Why Temporal

- Durable execution — workflows survive worker restarts (PRD §5.1)
- Built-in retry policies with exponential backoff (PRD §4.5)
- Cooperative cancellation with signals (PRD §4.6)
- Query API for observability without blocking (PRD §3.4)
- Event history persistence for audit (PRD §11)
- Horizontal worker scaling (PRD §5.2)
- Activity heartbeating for long-running operations

### B.4 Why Tenacity (not just Temporal retries)

- **Two-layer retry strategy** (PRD §10):
  - **Tenacity**: Inside tool functions — retries transient HTTP failures, LLM rate limits, provider timeouts. Fast, in-process, no Temporal overhead.
  - **Temporal**: Activity-level — retries on worker crashes, infrastructure issues, network partitions. Durable, cross-process.
- Tenacity is lightweight: `@retry(stop=stop_after_attempt(3), wait=wait_exponential(...))`
- Custom `before_sleep` callbacks for reconnection logic
- Async-native with `AsyncRetrying`

### B.5 Why PostgreSQL + SQLModel

- PostgreSQL for operational data (PRD §11 — "Operational Database")
- SQLModel combines SQLAlchemy 2.0 + Pydantic — single model definition
- `asyncpg` driver for native async performance
- Alembic for production migrations
- Temporal has its own history store — PostgreSQL stores our business metadata

### B.6 Why Redis

- Pub/Sub for streaming fanout (PRD §7 — optional path)
- Low-latency message delivery (< 1ms)
- Simple in-memory rate limiting (Phase 6)
- Connection pooling via `redis[hiredis]`
- Replaceable with Redis Cluster for horizontal scaling

### B.7 Why OpenTelemetry

- Vendor-neutral — export to Jaeger, Datadog, New Relic, etc.
- Auto-instrumentation for FastAPI + HTTPX
- Custom metrics for all PRD §15 success metrics
- Distributed tracing across API → Temporal → Activities → Tools

---

## Appendix C — API Contract

### C.1 Direct Tool Execution

```
GET    /health                           → {"status": "ok"}
GET    /api/v1/tools/list                → {"tools": [{"name", "description", "input_schema"}]}
POST   /api/v1/tools/invoke              → {"tool_name", "output", "metadata"}
```

**Request:**
```json
{
    "tool_name": "web_search",
    "arguments": {"query": "Temporal vs FastMCP", "max_results": 5}
}
```

**Response:**
```json
{
    "tool_name": "web_search",
    "output": {"results": [...]},
    "metadata": {"duration_ms": 342}
}
```

### C.2 Streaming Tool Execution

```
POST   /api/v1/stream/invoke             → SSE stream of StreamEvents
```

**Request:**
```json
{
    "tool_name": "streaming_llm",
    "arguments": {"prompt": "Hello", "model": "gpt-4"}
}
```

**SSE Response (events):**
```event-stream
data: {"type": "chunk", "data": {"token": "Hi"}}

data: {"type": "chunk", "data": {"token": " there"}}

data: {"type": "progress", "message": "Generating response", "metadata": {"tokens": 2}}

data: {"type": "done", "data": {"summary": "Complete"}, "metadata": {"duration_ms": 1234}}
```

### C.3 Workflow Execution

```
POST   /api/v1/workflows/start           → {"workflow_id", "run_id", "status"}
GET    /api/v1/workflows/{id}/status     → {"workflow_id", "run_id", "status", "result"}
GET    /api/v1/workflows/{id}/history    → {"workflow_id", "events": [...]}
POST   /api/v1/workflows/{id}/cancel     → {"workflow_id", "status": "cancelling"}
POST   /api/v1/workflows/{id}/signal     → {"workflow_id", "signal": "name"}
```

**Start Request:**
```json
{
    "workflow_type": "research_workflow",
    "input": {
        "query": "Research Temporal workflows",
        "model": "gpt-4",
        "max_results": 5
    }
}
```

**Start Response:**
```json
{
    "workflow_id": "abc-123-def",
    "run_id": "run-456-ghi",
    "status": "started"
}
```

**Status Response:**
```json
{
    "workflow_id": "abc-123-def",
    "run_id": "run-456-ghi",
    "status": "COMPLETED",
    "result": {
        "search_results": {...},
        "summary": {...},
        "report": {...}
    }
}
```

### C.4 WebSocket Streaming

```
WS     /ws/stream/{workflow_id}          → JSON StreamEvents
```

**Client sends:**
```json
{"action": "cancel"}
```

**Server sends:**
```json
{"type": "chunk", "data": {"token": "..."}}
{"type": "progress", "message": "Step 2 of 3"}
{"type": "done", "data": {...}}
```

### C.5 Authentication

All endpoints (except `/health`) require:
```
X-API-Key: <api-key>
```

---

## Appendix D — Phase Summary & Effort Estimates

| Phase | Description | Estimated Effort | Dependencies |
|-------|-------------|-----------------|--------------|
| 1 | Project Bootstrap | 2 hours | None |
| 2 | Tool Registry & Direct Execution | 1-2 days | Phase 1 |
| 3 | Streaming Responses | 1 day | Phase 2 |
| 4 | Workflow Orchestration (Temporal) | 3-4 days | Phase 2 |
| 5 | Persistence & Observability | 2 days | Phase 2, 4 |
| 6 | Cancellation & Retry Policies | 1-2 days | Phase 4 |
| 7 | Security & Production Hardening | 2 days | Phase 2 |
| 8 | Redis Pub/Sub & WebSocket | 1-2 days | Phase 3 |
| 9 | Docker & Kubernetes | 2 days | All phases |

**Total estimated effort:** 2-3 weeks (single engineer)

---

## Appendix E — Open Questions from PRD §13

1. **Streaming replay/resume** — Deferred. Not a core requirement.
2. **DAG editing** — Out of scope. Future enhancement (§14).
3. **Agent memory persistence** — **Implemented in Phase 9** (`docs/arch/phase9-spec.md` Part B).
4. **Human approval steps** — **Implemented in Phase 9** (`docs/arch/phase9-spec.md` Part A).