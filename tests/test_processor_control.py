"""Adapter tests for operation-scoped simulated-processor configuration."""

import json

import httpx
import pytest

from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.processor_control import (
    ProcessorControlClient,
    ProcessorOperation,
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
