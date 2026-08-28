"""Unit tests for bounded asynchronous-operation polling."""

from dataclasses import dataclass

import pytest

from totally_testable_banking_api_tests import operation_polling
from totally_testable_banking_api_tests.operation_polling import (
    OperationFailedError,
    OperationPollingTimeoutError,
    OperationSettlementTimeoutError,
    wait_for_settlement,
    wait_for_terminal_status,
)

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class StubOperation:
    status: str
    failure_code: str | None = None


@pytest.mark.parametrize("terminal_status", ["POSTED", "FAILED"])
def test_wait_for_terminal_status_returns_configured_terminal_response(
    terminal_status: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            StubOperation(status="PENDING"),
            StubOperation(status=terminal_status),
        ]
    )
    monkeypatch.setattr(operation_polling.time, "sleep", lambda _interval: None)

    result = wait_for_terminal_status(
        lambda: next(responses),
        operation_name="scheduled transfer",
        terminal_statuses={"POSTED", "FAILED"},
    )

    assert result.status == terminal_status


def test_wait_for_terminal_status_rejects_empty_terminal_statuses() -> None:
    with pytest.raises(ValueError, match="terminal_statuses must not be empty"):
        wait_for_terminal_status(
            lambda: StubOperation(status="PENDING"),
            operation_name="scheduled transfer",
            terminal_statuses=set(),
        )


@pytest.mark.parametrize("invalid_timeout", [0, -1])
def test_wait_for_terminal_status_rejects_nonpositive_timeout(
    invalid_timeout: float,
) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be greater than 0"):
        wait_for_terminal_status(
            lambda: StubOperation(status="PENDING"),
            operation_name="scheduled transfer",
            terminal_statuses={"POSTED", "FAILED"},
            timeout_seconds=invalid_timeout,
        )


@pytest.mark.parametrize("invalid_interval", [0, -1])
def test_wait_for_terminal_status_rejects_nonpositive_poll_interval(
    invalid_interval: float,
) -> None:
    with pytest.raises(ValueError, match="poll_interval_seconds must be greater than 0"):
        wait_for_terminal_status(
            lambda: StubOperation(status="PENDING"),
            operation_name="scheduled transfer",
            terminal_statuses={"POSTED", "FAILED"},
            poll_interval_seconds=invalid_interval,
        )


def test_wait_for_terminal_status_times_out_before_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monotonic_values = iter([0.0, 0.0, 1.1])
    monkeypatch.setattr(operation_polling.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(operation_polling.time, "sleep", lambda _interval: None)

    with pytest.raises(
        OperationPollingTimeoutError,
        match="scheduled transfer did not reach a terminal status",
    ):
        wait_for_terminal_status(
            lambda: StubOperation(status="PENDING"),
            operation_name="scheduled transfer",
            terminal_statuses={"POSTED", "FAILED"},
            timeout_seconds=1.0,
        )


def test_wait_for_terminal_status_limits_sleep_to_remaining_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            StubOperation(status="PENDING"),
            StubOperation(status="POSTED"),
        ]
    )
    monotonic_values = iter([0.0, 0.8])
    sleep_intervals: list[float] = []
    monkeypatch.setattr(operation_polling.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(operation_polling.time, "sleep", sleep_intervals.append)

    result = wait_for_terminal_status(
        lambda: next(responses),
        operation_name="scheduled transfer",
        terminal_statuses={"POSTED", "FAILED"},
        timeout_seconds=1.0,
        poll_interval_seconds=0.5,
    )

    assert result.status == "POSTED"
    assert sleep_intervals == [pytest.approx(0.2)]


def test_wait_for_settlement_returns_settled_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            StubOperation(status="PENDING"),
            StubOperation(status="SETTLED"),
        ]
    )
    monkeypatch.setattr(operation_polling.time, "sleep", lambda _interval: None)

    result = wait_for_settlement(
        lambda: next(responses),
        operation_name="deposit",
    )

    assert result.status == "SETTLED"


def test_wait_for_settlement_reports_terminal_failure() -> None:
    with pytest.raises(OperationFailedError, match="deposit failed with code 'DECLINED'"):
        wait_for_settlement(
            lambda: StubOperation(status="FAILED", failure_code="DECLINED"),
            operation_name="deposit",
        )


@pytest.mark.parametrize("invalid_timeout", [0, -1])
def test_wait_for_settlement_rejects_nonpositive_timeout(
    invalid_timeout: float,
) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be greater than 0"):
        wait_for_settlement(
            lambda: StubOperation(status="PENDING"),
            operation_name="deposit",
            timeout_seconds=invalid_timeout,
        )


@pytest.mark.parametrize("invalid_interval", [0, -1])
def test_wait_for_settlement_rejects_nonpositive_poll_interval(
    invalid_interval: float,
) -> None:
    with pytest.raises(ValueError, match="poll_interval_seconds must be greater than 0"):
        wait_for_settlement(
            lambda: StubOperation(status="PENDING"),
            operation_name="deposit",
            poll_interval_seconds=invalid_interval,
        )


def test_wait_for_settlement_times_out_while_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monotonic_values = iter([0.0, 0.0, 1.1])
    sleep_intervals: list[float] = []
    monkeypatch.setattr(operation_polling.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(operation_polling.time, "sleep", sleep_intervals.append)

    with pytest.raises(
        OperationSettlementTimeoutError,
        match="withdrawal did not settle; final status was 'PENDING'",
    ):
        wait_for_settlement(
            lambda: StubOperation(status="PENDING"),
            operation_name="withdrawal",
            timeout_seconds=1.0,
            poll_interval_seconds=0.25,
        )

    assert sleep_intervals == [0.25]
