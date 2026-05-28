"""Tests for retry policy (Tenacity integration)."""

import httpx
import pytest

from orion.retry.policy import (
    NON_TRANSIENT_EXCEPTIONS,
    TRANSIENT_EXCEPTIONS,
    retrying_execute,
    with_retry,
)


def test_transient_exceptions_include_connection_error() -> None:
    """ConnectionError should be classified as transient."""
    assert ConnectionError in TRANSIENT_EXCEPTIONS


def test_transient_exceptions_include_timeout() -> None:
    """TimeoutError should be classified as transient."""
    assert TimeoutError in TRANSIENT_EXCEPTIONS


def test_transient_exceptions_include_httpx_errors() -> None:
    """HTTPX errors should be classified as transient."""
    assert httpx.HTTPError in TRANSIENT_EXCEPTIONS


def test_non_transient_exceptions_include_value_error() -> None:
    """ValueError should be classified as non-transient."""
    assert ValueError in NON_TRANSIENT_EXCEPTIONS


def test_non_transient_exceptions_include_type_error() -> None:
    """TypeError should be classified as non-transient."""
    assert TypeError in NON_TRANSIENT_EXCEPTIONS


@pytest.mark.asyncio
async def test_retry_on_transient_error() -> None:
    """Function should retry on transient errors and succeed."""
    call_count = 0

    @with_retry(max_attempts=3, backoff=0.1)
    async def flaky_func() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            err = ConnectionError("transient")
            raise err
        return "success"

    result = await flaky_func()
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_non_transient() -> None:
    """Function should fail immediately on non-transient errors."""
    call_count = 0

    @with_retry(max_attempts=3)
    async def bad_input() -> str:
        nonlocal call_count
        call_count += 1
        err = ValueError("invalid")
        raise err

    with pytest.raises(ValueError, match="invalid"):
        await bad_input()
    assert call_count == 1


@pytest.mark.asyncio
async def test_retry_exhausted_raises() -> None:
    """Function should raise after all retry attempts exhausted."""
    call_count = 0

    @with_retry(max_attempts=2, backoff=0.05)
    async def always_fails() -> str:
        nonlocal call_count
        call_count += 1
        err = ConnectionError("always down")
        raise err

    with pytest.raises(ConnectionError):
        await always_fails()
    assert call_count == 2


@pytest.mark.asyncio
async def test_retrying_execute_on_transient() -> None:
    """retrying_execute should retry and succeed on transient errors."""
    call_count = 0

    async def flaky_func() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            err = TimeoutError("slow")
            raise err
        return "ok"

    result = await retrying_execute(flaky_func, max_attempts=3, backoff=0.05)
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_retrying_execute_with_args() -> None:
    """retrying_execute should pass through args and kwargs."""

    async def add(a: int, b: int) -> int:
        return a + b

    result = await retrying_execute(add, 2, 3)
    assert result == 5
