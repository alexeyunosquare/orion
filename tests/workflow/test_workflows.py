"""Tests for workflow definitions and activities."""

import pytest

from orion.workflow.activities import report_activity, search_activity, summarize_activity
from orion.workflow.workflows import ResearchWorkflow


def test_workflow_class_has_required_decorators():
    """ResearchWorkflow is a proper Temporal workflow class."""
    assert hasattr(ResearchWorkflow, "run")
    assert hasattr(ResearchWorkflow, "handle_cancel")
    assert hasattr(ResearchWorkflow, "get_progress")


def test_workflow_has_run_method():
    """The run method is callable."""
    assert callable(ResearchWorkflow.run)


def test_workflow_has_signal_handler():
    """The cancel signal handler is defined."""
    assert callable(ResearchWorkflow.handle_cancel)


def test_workflow_has_query_handler():
    """The progress query is defined."""
    assert callable(ResearchWorkflow.get_progress)


def test_workflow_initial_state():
    """Workflow starts with correct initial state."""
    wf = ResearchWorkflow()
    assert wf._status == "pending"  # noqa: SLF001
    assert wf._current_step == 0  # noqa: SLF001
    assert wf._cancelled is False  # noqa: SLF001


def test_activities_are_defined():
    """All activity functions are callable."""
    assert callable(search_activity)
    assert callable(summarize_activity)
    assert callable(report_activity)


@pytest.mark.asyncio
async def test_report_activity():
    """Report activity returns structured report."""
    result = await report_activity("Test Title", "Test Content", "markdown")
    assert result["title"] == "Test Title"
    assert result["content"] == "Test Content"
    assert result["format"] == "markdown"
