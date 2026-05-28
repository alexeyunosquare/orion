"""Tests for workflow API endpoints."""

from orion.api.routes.workflows import (
    WorkflowCancelResponse,
    WorkflowStartRequest,
    WorkflowStartResponse,
)


def test_workflow_start_request_model() -> None:
    """WorkflowStartRequest validates required fields."""
    req = WorkflowStartRequest(
        workflow_type="research_workflow",
        input={"query": "test"},
    )
    assert req.workflow_type == "research_workflow"
    assert req.id is None


def test_workflow_start_request_with_id() -> None:
    """WorkflowStartRequest accepts optional id."""
    req = WorkflowStartRequest(
        workflow_type="research_workflow",
        input={"query": "test"},
        id="custom-id",
    )
    assert req.id == "custom-id"


def test_workflow_start_response_model() -> None:
    """WorkflowStartResponse serializes correctly."""
    resp = WorkflowStartResponse(
        workflow_id="wf-123",
        run_id="run-456",
    )
    assert resp.status == "started"
    data = resp.model_dump()
    assert data["workflow_id"] == "wf-123"


def test_workflow_cancel_response_model() -> None:
    """WorkflowCancelResponse includes propagation time."""
    resp = WorkflowCancelResponse(
        workflow_id="wf-123",
        status="cancelling",
        propagation_ms=150.5,
    )
    assert resp.propagation_ms == 150.5
    data = resp.model_dump()
    assert "propagation_ms" in data
