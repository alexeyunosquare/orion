"""OpenTelemetry metrics for Orion."""

from opentelemetry import metrics

from orion.config import settings

_meter_provider = None
_meter = None


def get_meter():
    """Get or create the OpenTelemetry meter with all Orion metrics."""
    global _meter  # noqa: PLW0603
    if _meter is not None:
        return _meter

    _meter = metrics.get_meter_provider().get_meter(settings.otel_service_name)
    _meter.create_counter(
        name="orion.tool_calls_total",
        description="Total number of tool calls",
    )
    _meter.create_histogram(
        name="orion.tool_call_duration_seconds",
        description="Duration of tool calls in seconds",
    )
    _meter.create_counter(
        name="orion.workflow_runs_total",
        description="Total number of workflow runs",
    )
    _meter.create_histogram(
        name="cancellation.propagation.ms",
        description="Time from cancel request to activity termination",
        unit="ms",
    )
    return _meter
