"""Adapter tests for operation-scoped simulated-processor configuration."""

import json
import uuid

import httpx
import pytest

from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.processor_control import (
    ProcessorCommandStatus,
    ProcessorControlClient,
    ProcessorOperation,
    ProcessorOutcome,
    ProcessorScenario,
)

pytestmark = pytest.mark.unit


def test_configure_scenario_sends_operation_scoped_configuration() -> None:
    operation_key = "deposit-decline-123"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"/internal/v1/scenarios/DEPOSIT/{operation_key}"
        assert request.headers["Authorization"] == "Bearer processor-control-token"
        assert json.loads(request.content) == {"scenario": "DEPOSIT_DECLINE"}
        return httpx.Response(
            200,
            json={
                "operation": "DEPOSIT",
                "operation_key": operation_key,
                "scenario": "DEPOSIT_DECLINE",
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8011",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = ProcessorControlClient(transport, token="processor-control-token")

    try:
        configured = client.configure_scenario(
            operation=ProcessorOperation.DEPOSIT,
            operation_key=operation_key,
            scenario=ProcessorScenario.DEPOSIT_DECLINE,
        )
    finally:
        transport.close()

    assert configured.operation is ProcessorOperation.DEPOSIT
    assert configured.operation_key == operation_key
    assert configured.scenario is ProcessorScenario.DEPOSIT_DECLINE


def test_settle_pending_command_targets_exact_bank_instruction() -> None:
    bank_instruction_id = uuid.UUID("017f22e2-79b0-7cc3-98c4-dc0c0c07398f")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == (f"/internal/v1/commands/{bank_instruction_id}/settle")
        assert request.headers["Authorization"] == "Bearer processor-control-token"
        assert request.content == b""
        return httpx.Response(
            200,
            json={
                "operation": "WITHDRAWAL",
                "operation_key": "withdrawal-pending-123",
                "bank_instruction_id": str(bank_instruction_id),
                "status": "TERMINAL",
                "outcome": "SETTLED",
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8011",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = ProcessorControlClient(transport, token="processor-control-token")

    try:
        settled = client.settle_pending_command(
            bank_instruction_id=bank_instruction_id,
        )
    finally:
        transport.close()

    assert settled.operation is ProcessorOperation.WITHDRAWAL
    assert settled.operation_key == "withdrawal-pending-123"
    assert settled.bank_instruction_id == bank_instruction_id
    assert settled.status == "TERMINAL"
    assert settled.outcome == "SETTLED"


def test_observe_command_returns_callback_delivery_counts() -> None:
    bank_instruction_id = uuid.UUID("017f22e2-79b0-7cc3-98c4-dc0c0c07398f")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/internal/v1/commands/{bank_instruction_id}"
        assert request.headers["Authorization"] == "Bearer processor-control-token"
        assert request.content == b""
        return httpx.Response(
            200,
            json={
                "operation": "WITHDRAWAL",
                "operation_key": "withdrawal-duplicate-123",
                "bank_instruction_id": str(bank_instruction_id),
                "status": "TERMINAL",
                "outcome": "SETTLED",
                "failure_code": None,
                "callback_required_delivery_count": 2,
                "callback_successful_delivery_count": 2,
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8011",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = ProcessorControlClient(transport, token="processor-control-token")

    try:
        observed = client.observe_command(bank_instruction_id=bank_instruction_id)
    finally:
        transport.close()

    assert observed.operation is ProcessorOperation.WITHDRAWAL
    assert observed.operation_key == "withdrawal-duplicate-123"
    assert observed.bank_instruction_id == bank_instruction_id
    assert observed.status is ProcessorCommandStatus.TERMINAL
    assert observed.outcome is ProcessorOutcome.SETTLED
    assert observed.failure_code is None
    assert observed.callback_required_delivery_count == 2
    assert observed.callback_successful_delivery_count == 2
