"""OpenTelemetry tracing for Orion."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)

from orion.config import settings

_tracer_provider: TracerProvider | None = None


def setup_tracing() -> trace.Tracer:
    """Configure OpenTelemetry tracing and return the tracer."""
    global _tracer_provider  # noqa: PLW0603
    if _tracer_provider is not None:
        return trace.get_tracer(settings.otel_service_name)

    if not settings.otel_endpoint:
        exporter: SpanExporter = ConsoleSpanExporter()
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)

    _tracer_provider = TracerProvider()
    _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(_tracer_provider)
    return trace.get_tracer(settings.otel_service_name)


def instrument_app(app) -> None:  # noqa: ANN001
    """Instrument a FastAPI app with OpenTelemetry automatic tracing.

    Attaches the FastAPIInstrumentor to the app so every incoming HTTP
    request is automatically traced with span data (method, path, status
    code, duration).  Skips instrumentation if the tracer provider was
    not yet set up — call :func:`setup_tracing` first.
    """
    if _tracer_provider is None:
        return

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: PLC0415

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=_tracer_provider,
        excluded_urls=",".join(settings.auth_exempt_paths),
        exclude_spans=["receive", "send"],
    )
