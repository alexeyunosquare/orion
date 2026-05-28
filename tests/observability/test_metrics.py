"""Tests for OpenTelemetry metrics."""

from orion.observability.metrics import get_meter


def test_get_meter_returns_meter():
    """get_meter returns a meter instance."""
    meter = get_meter()
    assert meter is not None


def test_get_meter_is_singleton():
    """get_meter returns the same instance on repeated calls."""
    meter1 = get_meter()
    meter2 = get_meter()
    assert meter1 is meter2
