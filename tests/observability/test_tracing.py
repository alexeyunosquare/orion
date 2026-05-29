"""Tests for OpenTelemetry tracing."""

from unittest.mock import patch

from opentelemetry import trace

from orion.observability.tracing import instrument_app, setup_tracing


def test_setup_tracing_returns_tracer():
    """setup_tracing returns a tracer instance."""
    tracer = setup_tracing()
    assert tracer is not None
    assert isinstance(tracer, trace.Tracer)


def test_instrument_app_no_provider():
    """instrument_app is a no-op when tracer provider is not set up."""
    # Before setup_tracing, instrument_app should do nothing (no crash)
    with patch(
        "orion.observability.tracing._tracer_provider", None
    ):
        from orion.observability import tracing as tracing_module

        tracing_module._tracer_provider = None
        instrument_app(object())  # Should not raise


def test_instrument_app_calls_fastapi_instrumentor():
    """instrument_app delegates to FastAPIInstrumentor when provider exists."""
    setup_tracing()  # Ensure _tracer_provider is set

    mock_app = patch("fastapi.FastAPI").start()
    mock_app.__bool__ = lambda: True

    with patch(
        "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app"
    ) as mock_instrument:
        instrument_app(mock_app)
        mock_instrument.assert_called_once()
        call_kwargs = mock_instrument.call_args[1]
        assert "tracer_provider" in call_kwargs
        assert "excluded_urls" in call_kwargs
        assert "exclude_spans" in call_kwargs
        assert "receive" in call_kwargs["exclude_spans"]
        assert "send" in call_kwargs["exclude_spans"]
    patch.stopall()
