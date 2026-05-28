import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from orion.config import settings
from orion.workflow.activities import (
    report_activity,
    search_activity,
    summarize_activity,
)
from orion.workflow.client import get_temporal_client
from orion.workflow.workflows import ResearchWorkflow

logger = logging.getLogger(__name__)


async def start_worker(client: Client) -> None:
    """Start the Temporal worker with all activities and workflows."""
    worker = Worker(
        client=client,
        task_queue=settings.temporal_task_queue,
        activities=[search_activity, summarize_activity, report_activity],
        workflows=[ResearchWorkflow],
    )
    logger.info("Worker started on task queue: %s", settings.temporal_task_queue)
    await worker.run()


async def main() -> None:
    """Entry point for the worker process."""
    client = await get_temporal_client()
    await start_worker(client)


if __name__ == "__main__":
    asyncio.run(main())
