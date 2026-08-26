"""Client for operation-scoped behavior at the local simulated processor."""

import enum

from pydantic import BaseModel, ConfigDict

from totally_testable_banking_api_tests.http_client import ApiClient


class ProcessorOperation(enum.StrEnum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"


class ProcessorScenario(enum.StrEnum):
    DEPOSIT_SETTLE = "DEPOSIT_SETTLE"
    DEPOSIT_DECLINE = "DEPOSIT_DECLINE"
    WITHDRAWAL_SETTLE = "WITHDRAWAL_SETTLE"
    WITHDRAWAL_DECLINE = "WITHDRAWAL_DECLINE"
    WITHDRAWAL_ACCEPT_THEN_TIMEOUT = "WITHDRAWAL_ACCEPT_THEN_TIMEOUT"
    WITHDRAWAL_DUPLICATE_CALLBACK = "WITHDRAWAL_DUPLICATE_CALLBACK"


class ConfiguredProcessorScenario(BaseModel):
    """Published response confirming one operation-scoped scenario."""

    model_config = ConfigDict(extra="forbid")

    operation: ProcessorOperation
    operation_key: str
    scenario: ProcessorScenario


class ProcessorControlClient:
    """Configure the local simulated provider without changing the banking API."""

    def __init__(self, transport: ApiClient, *, token: str) -> None:
        self._transport = transport
        self._token = token

    def configure_scenario(
        self,
        *,
        operation: ProcessorOperation,
        operation_key: str,
        scenario: ProcessorScenario,
    ) -> ConfiguredProcessorScenario:
        response = self._transport.request(
            "PUT",
            f"/internal/v1/scenarios/{operation.value}/{operation_key}",
            expected_status=200,
            headers={"Authorization": f"Bearer {self._token}"},
            json_body={"scenario": scenario.value},
        )
        return ConfiguredProcessorScenario.model_validate(response.json())
