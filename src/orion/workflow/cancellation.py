"""Cancellation helpers for Temporal workflows.

Temporal handles cancellation natively:
- Workflow-level: handle.cancel() sends a CancelWorkflowExecution command
- Activity-level: Temporal raises CancelledError inside the activity
- Signal-level: custom signal handlers set a flag the workflow checks

This module provides helper utilities for cooperative cancellation
and cancellation propagation metrics.
"""

from __future__ import annotations

import time
from datetime import timedelta


class CancellationError(Exception):
    """Raised when an activity is cancelled via Temporal cancellation.

    Used to distinguish cancellation from other failures.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def measure_propagation_ms(start_time: float) -> float:
    """Measure cancellation propagation time in milliseconds.

    Args:
        start_time: Monotonic time when cancellation was requested.

    Returns:
        Elapsed time in milliseconds.
    """
    return round((time.monotonic() - start_time) * 1000, 2)


DEFAULT_CANCELLATION_TIMEOUT: timedelta = timedelta(seconds=3)
