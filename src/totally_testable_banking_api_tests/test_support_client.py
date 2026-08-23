from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.test_support_models import (
    CreateRunRequest,
    CreateRunResponse,
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
