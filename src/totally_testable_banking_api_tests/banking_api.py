from totally_testable_banking_api_tests.api_models import TokenResponse
from totally_testable_banking_api_tests.http_client import ApiClient


class BankingApiClient:
    """Operations against the internal banking product API contract."""

    def __init__(self, transport: ApiClient) -> None:
        self._transport = transport

    def login(self, *, email: str, password: str) -> TokenResponse:
        response = self._transport.request(
            "POST",
            "/api/v1/auth/tokens",
            expected_status=200,
            json_body={"email": email, "password": password},
        )
        return TokenResponse.model_validate(response.json())
