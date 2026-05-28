"""Retry policies using Tenacity for transient fault tolerance."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Exceptions that should trigger a retry (transient failures)
TRANSIENT_EXCEPTIONS: type[BaseException] | tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    httpx.HTTPError,
    httpx.ConnectError,
    httpx.ReadTimeout,
)

# Exceptions that should fail immediately (non-transient)
NON_TRANSIENT_EXCEPTIONS: type[BaseException] | tuple[type[BaseException], ...] = (
    ValueError,
    TypeError,
)


def with_retry(
    max_attempts: int = 3,
    backoff: float = 1.0,
    max_wait: int = 30,
    retryable_exceptions: type[BaseException] | tuple[type[BaseException], ...] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Tenacity retry decorator for tool functions.

    Retries on transient HTTP failures, provider timeouts, and temporary rate limits.
    """
    exceptions = retryable_exceptions or TRANSIENT_EXCEPTIONS

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


async def retrying_execute(
    func: Callable[..., Any],
    *args: Any,  # noqa: ANN401
    max_attempts: int = 3,
    backoff: float = 1.0,
    max_wait: int = 30,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Execute an async function with Tenacity retry logic.

    Returns the result or raises RetryError after all attempts exhausted.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff, max=max_wait),
        retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    ):
        with attempt:
            return await func(*args, **kwargs)
    msg = "Retry loop exited without result"
    raise RuntimeError(msg)
