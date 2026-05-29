"""FastAPI application factory with middleware and routing."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orion.api import websocket as ws_module
from orion.api.routes import approvals, health, memory, streaming, tools, workflows
from orion.config import settings
from orion.db.session import init_db
from orion.observability.logging import setup_logging
from orion.observability.tracing import instrument_app, setup_tracing
from orion.security.audit import AuditMiddleware
from orion.security.auth import verify_api_key
from orion.security.rate_limit import RateLimitMiddleware
from orion.tools.registry import mcp_server


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup
    setup_logging("DEBUG" if settings.debug else "INFO")
    setup_tracing()
    instrument_app(app)

    # Import tools to register them
    from orion.tools import registry  # noqa: F401, PLC0415

    # Database may not be available in tests
    with suppress(Exception):
        await init_db()

    yield
    # Shutdown — cleanup connections


# Create MCP ASGI app
mcp_app = mcp_server.http_app(path="/")

app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

# --- Security middleware (order matters: outer -> inner) ---

# 1. Rate limiting (first line of defence)
app.add_middleware(RateLimitMiddleware)

# 2. Audit logging (captures all requests)
app.add_middleware(AuditMiddleware)

# 3. CORS (hardened — configurable origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# --- Routers ---

# Health endpoint (no auth required)
app.include_router(health.router)

# Protected API routes
app.include_router(tools.router, dependencies=[Depends(verify_api_key)])
app.include_router(streaming.router, dependencies=[Depends(verify_api_key)])
app.include_router(workflows.router, dependencies=[Depends(verify_api_key)])
app.include_router(approvals.router, dependencies=[Depends(verify_api_key)])
app.include_router(memory.router, dependencies=[Depends(verify_api_key)])

# WebSocket streaming (no auth — relies on workflow ID scoping)
app.include_router(ws_module.router)

# Mount MCP HTTP app for native MCP clients
app.mount("/mcp", mcp_app)
