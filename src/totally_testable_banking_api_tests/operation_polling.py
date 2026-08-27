"""Bounded polling for asynchronous banking operations."""

import time
from collections.abc import Callable
from typing import Protocol


class OperationStatus(Protocol):
    """The status fields required by the settlement poller."""

    @property
    def status(self) -> str: ...

    @property
    def failure_code(self) -> str | None: ...


class OperationFailedError(RuntimeError):
    """An asynchronous operation reached its terminal failure state."""


class OperationSettlementTimeoutError(TimeoutError):
    """An asynchronous operation did not settle before its deadline."""


def wait_for_settlement[OperationResponse: OperationStatus](
    fetch: Callable[[], OperationResponse],
    *,
    operation_name: str,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.1,
) -> OperationResponse:
    """Return the settled response, failing fast on failure or timeout."""

    deadline = time.monotonic() + timeout_seconds

    while True:
        current = fetch()
        if current.status == "SETTLED":
            return current
        if current.status == "FAILED":
            raise OperationFailedError(
                f"{operation_name} failed with code {current.failure_code!r}"
            )
        if time.monotonic() >= deadline:
            raise OperationSettlementTimeoutError(
                f"{operation_name} did not settle; final status was {current.status!r}"
            )
        time.sleep(poll_interval_seconds)
