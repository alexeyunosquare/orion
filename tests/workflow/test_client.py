"""Tests for Temporal client management."""

import pytest

from orion.workflow.client import reset_temporal_client


@pytest.mark.asyncio
async def test_reset_temporal_client():
    """Reset clears the singleton."""
    await reset_temporal_client()
    from orion.workflow import client as client_module

    assert client_module._temporal_client is None
