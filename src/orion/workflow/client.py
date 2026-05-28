from temporalio.client import Client

from orion.config import settings

_temporal_client: Client | None = None


async def get_temporal_client() -> Client:
    """Get or create the Temporal client singleton."""
    global _temporal_client  # noqa: PLW0603
    if _temporal_client is None:
        _temporal_client = await Client.connect(
            f"{settings.temporal_host}:{settings.temporal_port}",
            namespace=settings.temporal_namespace,
        )
    return _temporal_client


async def reset_temporal_client() -> None:
    """Reset the client singleton. Useful for testing."""
    global _temporal_client  # noqa: PLW0603
    _temporal_client = None
