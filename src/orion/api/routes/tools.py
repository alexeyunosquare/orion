from typing import Any

from fastapi import APIRouter, HTTPException
from fastmcp import Client
from pydantic import BaseModel

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
async def list_tools() -> dict[str, list[dict[str, Any]]]:
    """List all registered tools with their schemas."""
    async with Client(mcp_server) as client:
        tools_list = await client.list_tools()
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools_list
            ]
        }


@router.post("/invoke")
async def invoke_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Invoke a tool directly and return structured results."""
    async with Client(mcp_server) as client:
        try:
            result = await client.call_tool(request.tool_name, request.arguments)
            return ToolCallResponse(
                tool_name=request.tool_name,
                output=result.data,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
