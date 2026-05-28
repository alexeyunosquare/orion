"""Tests for database models."""

from orion.db.models import (
    ActivityRecord,
    ExecutionOutput,
    ExecutionRequest,
    WorkflowStatus,
)


def test_execution_request_creation():
    """ExecutionRequest creates with defaults."""
    request = ExecutionRequest(
        correlation_id="test-001",
        tool_name="web_search",
        input_data={"query": "test"},
    )
    assert request.id is None
    assert request.status == WorkflowStatus.PENDING
    assert request.correlation_id == "test-001"
    assert request.input_data == {"query": "test"}


def test_execution_request_with_workflow_id():
    """ExecutionRequest accepts workflow_id."""
    request = ExecutionRequest(
        correlation_id="test-002",
        workflow_id="wf-123",
    )
    assert request.workflow_id == "wf-123"
    assert request.input_data is None


def test_workflow_status_values():
    """WorkflowStatus enum has all expected values."""
    assert WorkflowStatus.PENDING == "pending"
    assert WorkflowStatus.RUNNING == "running"
    assert WorkflowStatus.COMPLETED == "completed"
    assert WorkflowStatus.FAILED == "failed"
    assert WorkflowStatus.CANCELLED == "cancelled"


def test_activity_record_creation():
    """ActivityRecord creates with defaults."""
    record = ActivityRecord(
        request_id=1,
        activity_type="search_activity",
    )
    assert record.attempt == 1
    assert record.status == WorkflowStatus.PENDING
    assert record.error is None
    assert record.completed_at is None


def test_execution_output_creation():
    """ExecutionOutput creates with defaults."""
    output = ExecutionOutput(
        request_id=1,
        output_data={"results": []},
    )
    assert output.id is None
    assert output.output_data == {"results": []}
