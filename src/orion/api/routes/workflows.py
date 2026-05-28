from __future__ import annotations

import contextlib
import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from orion.workflow.client import get_temporal_client

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


class WorkflowStartRequest(BaseModel):
    workflow_type: str
    input: dict[str, Any]
    id: str | None = None


class WorkflowStartResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str = "started"


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    result: Any | None = None


@router.post("/start")
async def start_workflow(request: WorkflowStartRequest) -> WorkflowStartResponse:
    """Start a new workflow execution."""
    client = await get_temporal_client()

    workflow_id = request.id or str(uuid.uuid4())

    handle = await client.start_workflow(
        request.workflow_type,
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
async def get_workflow_status(workflow_id: str) -> dict[str, Any]:
    """Get the current status of a workflow execution."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    description = await handle.describe()

    result = None
    if description.status.value == "COMPLETED":
        with contextlib.suppress(Exception):
            result = await handle.result()

    return {
        "workflow_id": workflow_id,
        "run_id": description.run_id,
        "status": description.status.value,
        "result": result,
    }


@router.post("/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str) -> dict[str, str]:
    """Cancel a running workflow."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.cancel()
    return {"workflow_id": workflow_id, "status": "cancelling"}


@router.post("/{workflow_id}/signal")
async def signal_workflow(
    workflow_id: str,
    signal_name: str,
    args: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Send a signal to a running workflow."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(signal_name, *(args.values()) if args else ())
    return {"workflow_id": workflow_id, "signal": signal_name}


@router.get("/{workflow_id}/history")
async def get_workflow_history(workflow_id: str) -> dict[str, Any]:
    """Get the full event history of a workflow execution."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    history = await handle.fetch_history()
    events = [
        event.__dict__ if hasattr(event, "__dict__") else str(event)
        for event in history.history.events
    ]
    return {
        "workflow_id": workflow_id,
        "events": events,
    }
