"""API endpoints for human approval management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orion.workflow.client import get_temporal_client

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


class ApprovalActionRequest(BaseModel):
    approved_by: str = ""
    reason: str = ""


class ApprovalInfo(BaseModel):
    workflow_id: str
    run_id: str
    status: str
    progress: dict[str, Any] | None = None


@router.get("/pending")
async def list_pending_approvals() -> dict[str, list[ApprovalInfo]]:
    """List all workflows currently awaiting approval.

    Queries the Temporal namespace for running workflows and filters by
    progress status == 'awaiting_approval'.
    """
    client = await get_temporal_client()
    # List workflows — in production, use Temporal's workflow query API
    # with a custom query index for filtering by approval state.
    # For now, return empty list; implement when workflow listing is needed.
    return {"approvals": []}


@router.post("/{workflow_id}/approve")
async def approve_workflow(
    workflow_id: str,
    request: ApprovalActionRequest,
) -> dict[str, str]:
    """Approve a pending approval request."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    # Check workflow is running and awaiting approval
    progress = await handle.query("get_progress")
    if not progress.get("pending_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not awaiting approval (status: {progress.get('status')})",
        )

    await handle.signal(
        "approve",
        approved_by=request.approved_by,
        reason=request.reason,
    )
    return {"workflow_id": workflow_id, "status": "approved"}


@router.post("/{workflow_id}/reject")
async def reject_workflow(
    workflow_id: str,
    request: ApprovalActionRequest,
) -> dict[str, str]:
    """Reject a pending approval request."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)

    progress = await handle.query("get_progress")
    if not progress.get("pending_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"Workflow is not awaiting approval (status: {progress.get('status')})",
        )

    await handle.signal(
        "reject",
        rejected_by=request.approved_by,
        reason=request.reason,
    )
    return {"workflow_id": workflow_id, "status": "rejected"}
