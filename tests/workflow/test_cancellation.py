"""Tests for workflow cancellation."""

import time

from orion.workflow.cancellation import (
    DEFAULT_CANCELLATION_TIMEOUT,
    CancellationError,
    measure_propagation_ms,
)


def test_cancellation_error_message() -> None:
    """CancellationError carries the activity name."""
    err = CancellationError("Activity cancelled: search_activity")
    assert "search_activity" in err.message
    assert "cancelled" in str(err).lower()


def test_cancellation_error_is_exception() -> None:
    """CancellationError is a proper Exception subclass."""
    assert issubclass(CancellationError, Exception)


def test_measure_propagation_ms() -> None:
    """measure_propagation_ms returns elapsed time in ms."""
    start = time.monotonic()
    time.sleep(0.05)  # 50ms
    elapsed = measure_propagation_ms(start)
    assert elapsed >= 40  # Allow some tolerance
    assert elapsed < 200


def test_default_cancellation_timeout() -> None:
    """Default cancellation timeout is 3 seconds."""
    assert DEFAULT_CANCELLATION_TIMEOUT.total_seconds() == 3
