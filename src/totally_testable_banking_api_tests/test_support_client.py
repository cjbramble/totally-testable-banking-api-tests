import uuid

from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.test_support_models import (
    CompleteRunRequest,
    CreateRunRequest,
    CreateRunResponse,
    RunResponse,
)


class TestSupportClient:
    """Operations against the internal test-support control plane."""

    def __init__(self, transport: ApiClient, *, token: str) -> None:
        self._transport = transport
        self._headers = {"Authorization": f"Bearer {token}"}

    def create_run(self, request: CreateRunRequest) -> CreateRunResponse:
        response = self._transport.request(
            "POST",
            "/runs",
            expected_status=201,
            headers=self._headers,
            json_body=request.model_dump(mode="json", exclude_none=True),
        )
        return CreateRunResponse.model_validate(response.json())

    def complete_run(
        self,
        *,
        run_id: uuid.UUID,
        run_token: str,
        request: CompleteRunRequest,
    ) -> RunResponse:
        response = self._transport.request(
            "POST",
            f"/runs/{run_id}/complete",
            expected_status=200,
            headers={
                **self._headers,
                "X-Test-Run-Token": run_token,
            },
            json_body=request.model_dump(mode="json", exclude_none=True),
        )
        return RunResponse.model_validate(response.json())
