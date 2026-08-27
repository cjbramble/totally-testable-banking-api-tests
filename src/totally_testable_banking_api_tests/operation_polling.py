"""Bounded polling for asynchronous banking operations."""

import time
from collections.abc import Callable, Collection
from typing import Protocol


class StatusResponse(Protocol):
    """The response field required by generic terminal-status polling."""

    @property
    def status(self) -> str: ...


class OperationStatus(StatusResponse, Protocol):
    """The additional failure field required by settlement polling."""

    @property
    def failure_code(self) -> str | None: ...


class OperationFailedError(RuntimeError):
    """An asynchronous operation reached its terminal failure state."""


class OperationPollingTimeoutError(TimeoutError):
    """An asynchronous operation did not reach a terminal state in time."""


class OperationSettlementTimeoutError(OperationPollingTimeoutError):
    """An asynchronous operation did not settle before its deadline."""


def _wait_for_terminal_status[Response: StatusResponse](
    fetch: Callable[[], Response],
    *,
    operation_name: str,
    terminal_statuses: Collection[str],
    timeout_seconds: float,
    poll_interval_seconds: float,
    timeout_error: type[OperationPollingTimeoutError],
    timeout_action: str,
) -> Response:
    deadline = time.monotonic() + timeout_seconds

    while True:
        current = fetch()
        if current.status in terminal_statuses:
            return current
        if time.monotonic() >= deadline:
            raise timeout_error(
                f"{operation_name} did not {timeout_action}; final status was {current.status!r}"
            )
        time.sleep(poll_interval_seconds)


def wait_for_terminal_status[Response: StatusResponse](
    fetch: Callable[[], Response],
    *,
    operation_name: str,
    terminal_statuses: Collection[str],
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.1,
) -> Response:
    """Return once a response reaches any caller-defined terminal status."""

    if not terminal_statuses:
        raise ValueError("terminal_statuses must not be empty")

    return _wait_for_terminal_status(
        fetch,
        operation_name=operation_name,
        terminal_statuses=terminal_statuses,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        timeout_error=OperationPollingTimeoutError,
        timeout_action="reach a terminal status",
    )


def wait_for_settlement[OperationResponse: OperationStatus](
    fetch: Callable[[], OperationResponse],
    *,
    operation_name: str,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.1,
) -> OperationResponse:
    """Return the settled response, failing fast on failure or timeout."""

    current = _wait_for_terminal_status(
        fetch,
        operation_name=operation_name,
        terminal_statuses={"SETTLED", "FAILED"},
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        timeout_error=OperationSettlementTimeoutError,
        timeout_action="settle",
    )
    if current.status == "FAILED":
        raise OperationFailedError(f"{operation_name} failed with code {current.failure_code!r}")
    return current
