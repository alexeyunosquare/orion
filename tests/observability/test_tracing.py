"""Tests for OpenTelemetry tracing."""

from opentelemetry import trace

from orion.observability.tracing import setup_tracing


def test_setup_tracing_returns_tracer():
    """setup_tracing returns a tracer instance."""
    tracer = setup_tracing()
    assert tracer is not None
    assert isinstance(tracer, trace.Tracer)
