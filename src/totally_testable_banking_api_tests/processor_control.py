"""Client for operation-scoped behavior at the local simulated processor."""

import enum
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
    WITHDRAWAL_PENDING = "WITHDRAWAL_PENDING"


class ProcessorCommandStatus(enum.StrEnum):
    ACCEPTED = "ACCEPTED"
    TERMINAL = "TERMINAL"


class ProcessorOutcome(enum.StrEnum):
    SETTLED = "SETTLED"
    FAILED = "FAILED"


class ConfiguredProcessorScenario(BaseModel):
    """Published response confirming one operation-scoped scenario."""

    model_config = ConfigDict(extra="forbid")

    operation: ProcessorOperation
    operation_key: str
    scenario: ProcessorScenario


class ControlledSettlement(BaseModel):
    """Published response confirming exact controlled command settlement."""

    model_config = ConfigDict(extra="forbid")

    operation: Literal[ProcessorOperation.WITHDRAWAL]
    operation_key: str
    bank_instruction_id: uuid.UUID
    status: Literal["TERMINAL"]
    outcome: Literal["SETTLED"]


class ControlledCommandObservation(BaseModel):
    """Published provider state and callback-delivery observations."""

    model_config = ConfigDict(extra="forbid")

    operation: ProcessorOperation
    operation_key: str | None
    bank_instruction_id: uuid.UUID
    status: ProcessorCommandStatus
    outcome: ProcessorOutcome | None
    failure_code: str | None
    callback_required_delivery_count: int = Field(ge=0)
    callback_successful_delivery_count: int = Field(ge=0)


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

    def settle_pending_command(
        self,
        *,
        bank_instruction_id: uuid.UUID,
    ) -> ControlledSettlement:
        response = self._transport.request(
            "POST",
            f"/internal/v1/commands/{bank_instruction_id}/settle",
            expected_status=200,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        return ControlledSettlement.model_validate(response.json())

    def observe_command(
        self,
        *,
        bank_instruction_id: uuid.UUID,
    ) -> ControlledCommandObservation:
        response = self._transport.request(
            "GET",
            f"/internal/v1/commands/{bank_instruction_id}",
            expected_status=200,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        return ControlledCommandObservation.model_validate(response.json())
