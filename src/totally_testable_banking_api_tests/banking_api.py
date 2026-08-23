import uuid

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    TokenResponse,
    UserResponse,
)
from totally_testable_banking_api_tests.http_client import ApiClient


class BankingApiClient:
    """Operations against the internal banking product API contract."""

    def __init__(self, transport: ApiClient) -> None:
        self._transport = transport

    def register_user(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
    ) -> UserResponse:
        response = self._transport.request(
            "POST",
            "/api/v1/users",
            expected_status=201,
            json_body={
                "email": email,
                "display_name": display_name,
                "password": password,
            },
        )
        return UserResponse.model_validate(response.json())

    def login(self, *, email: str, password: str) -> TokenResponse:
        response = self._transport.request(
            "POST",
            "/api/v1/auth/tokens",
            expected_status=200,
            json_body={"email": email, "password": password},
        )
        return TokenResponse.model_validate(response.json())

    def list_accounts(self, *, access_token: str) -> list[AccountResponse]:
        response = self._transport.request(
            "GET",
            "/api/v1/accounts",
            expected_status=200,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return [AccountResponse.model_validate(item) for item in response.json()]

    def get_account(
        self,
        *,
        account_id: uuid.UUID,
        access_token: str,
    ) -> AccountResponse:
        response = self._transport.request(
            "GET",
            f"/api/v1/accounts/{account_id}",
            expected_status=200,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return AccountResponse.model_validate(response.json())
