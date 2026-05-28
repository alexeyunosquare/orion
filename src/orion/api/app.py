from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from orion.api.routes import health, streaming, tools
from orion.config import settings
from orion.tools.registry import mcp_server


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Startup
    # Import tools to register them
    from orion.tools import registry  # noqa: F401, PLC0415

    yield
    # Shutdown


# Create MCP ASGI app
mcp_app = mcp_server.http_app(path="/")

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

# Register routers
app.include_router(health.router)
app.include_router(tools.router)
app.include_router(streaming.router)

# Mount MCP HTTP app for native MCP clients
app.mount("/mcp", mcp_app)
