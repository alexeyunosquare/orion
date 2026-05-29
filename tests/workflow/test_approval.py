"""Tests for human approval gate."""

import pytest

from orion.workflow.approval import (
    ApprovalDecision,
    ApprovalGate,
    ApprovalRequest,
    ApprovalResult,
)


def test_approval_request_fields():
    req = ApprovalRequest(
        request_id="test-1",
        title="Test",
        description="Test description",
        requested_by="user-1",
    )
    assert req.request_id == "test-1"
    assert req.metadata == {}


def test_approval_request_with_metadata():
    req = ApprovalRequest(
        request_id="test-2",
        title="Test",
        description="Test",
        requested_by="user-1",
        metadata={"key": "value"},
    )
    assert req.metadata == {"key": "value"}


def test_approval_result_approved():
    result = ApprovalResult(
        decision=ApprovalDecision.APPROVED,
        approved_by="admin",
        reason="Looks good",
    )
    assert result.decision == ApprovalDecision.APPROVED
    assert result.approved_by == "admin"


def test_approval_result_rejected():
    result = ApprovalResult(
        decision=ApprovalDecision.REJECTED,
        approved_by="admin",
        reason="Not ready",
    )
    assert result.decision == ApprovalDecision.REJECTED
    assert result.reason == "Not ready"


def test_approval_decision_enum_values():
    assert ApprovalDecision.APPROVED == "approved"
    assert ApprovalDecision.REJECTED == "rejected"


def test_approval_gate_has_signal_handlers():
    """ApprovalGate defines approve and reject signal handlers."""
    assert hasattr(ApprovalGate, "handle_approve")
    assert hasattr(ApprovalGate, "handle_reject")
    assert callable(ApprovalGate.handle_approve)
    assert callable(ApprovalGate.handle_reject)


def test_approval_gate_has_wait_method():
    """ApprovalGate defines wait_for_approval method."""
    assert hasattr(ApprovalGate, "wait_for_approval")
    assert callable(ApprovalGate.wait_for_approval)
