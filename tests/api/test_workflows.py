"""Tests for workflow API endpoints."""

from orion.api.routes.workflows import (
    WorkflowStartRequest,
    WorkflowStartResponse,
)


def test_workflow_start_request_model():
    """WorkflowStartRequest accepts valid input."""
    req = WorkflowStartRequest(
        workflow_type="research_workflow",
        input={"query": "test"},
    )
    assert req.workflow_type == "research_workflow"
    assert req.id is None


def test_workflow_start_request_with_id():
    """WorkflowStartRequest accepts custom workflow ID."""
    req = WorkflowStartRequest(
        workflow_type="research_workflow",
        input={"query": "test"},
        id="custom-id-123",
    )
    assert req.id == "custom-id-123"


def test_workflow_start_response_model():
    """WorkflowStartResponse serializes correctly."""
    resp = WorkflowStartResponse(
        workflow_id="wf-123",
        run_id="run-456",
    )
    assert resp.workflow_id == "wf-123"
    assert resp.run_id == "run-456"
    assert resp.status == "started"
