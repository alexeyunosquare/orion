"""Tests for structured logging."""

import json
import logging

from orion.observability.logging import JSONFormatter


def test_json_formatter_basic():
    """JSONFormatter produces valid JSON."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert "timestamp" in data


def test_json_formatter_with_correlation_id():
    """JSONFormatter includes correlation_id when present."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "corr-123"
    output = formatter.format(record)
    data = json.loads(output)
    assert data["correlation_id"] == "corr-123"


def test_json_formatter_with_workflow_id():
    """JSONFormatter includes workflow_id when present."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.workflow_id = "wf-456"
    output = formatter.format(record)
    data = json.loads(output)
    assert data["workflow_id"] == "wf-456"
