"""Unit tests for bounded asynchronous-operation polling."""

from dataclasses import dataclass

import pytest

from totally_testable_banking_api_tests import operation_polling
from totally_testable_banking_api_tests.operation_polling import (
    OperationFailedError,
    OperationSettlementTimeoutError,
    wait_for_settlement,
)

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class StubOperation:
    status: str
    failure_code: str | None = None


def test_wait_for_settlement_returns_settled_response() -> None:
    responses = iter(
        [
            StubOperation(status="PENDING"),
            StubOperation(status="SETTLED"),
        ]
    )

    result = wait_for_settlement(
        lambda: next(responses),
        operation_name="deposit",
        poll_interval_seconds=0,
    )

    assert result.status == "SETTLED"


def test_wait_for_settlement_reports_terminal_failure() -> None:
    with pytest.raises(OperationFailedError, match="deposit failed with code 'DECLINED'"):
        wait_for_settlement(
            lambda: StubOperation(status="FAILED", failure_code="DECLINED"),
            operation_name="deposit",
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
