import uuid
from collections.abc import Mapping
from datetime import date

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ActivityPageResponse,
    DepositResponse,
    SessionResponse,
    TokenResponse,
    TransferResponse,
    UserResponse,
    WithdrawalResponse,
)
from totally_testable_banking_api_tests.http_client import ApiClient

CSRF_COOKIE_NAME = "ttb_csrf"


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

    def create_browser_session(self, *, email: str, password: str) -> SessionResponse:
        response = self._transport.request(
            "POST",
            "/api/v1/auth/session",
            expected_status=200,
            json_body={"email": email, "password": password},
        )
        return SessionResponse.model_validate(response.json())

    def read_browser_session(self) -> UserResponse:
        response = self._transport.request(
            "GET",
            "/api/v1/auth/session",
            expected_status=200,
        )
        return UserResponse.model_validate(response.json())

    def delete_browser_session(self, *, csrf_token: str | None = None) -> None:
        if csrf_token is None:
            csrf_token = self._transport.cookie_value(CSRF_COOKIE_NAME)
        if csrf_token is None:
            raise RuntimeError("Browser session did not provide a CSRF cookie")

        self._transport.request(
            "DELETE",
            "/api/v1/auth/session",
            expected_status=204,
            headers={"X-CSRF-Token": csrf_token},
        )

    def list_accounts(self, *, access_token: str) -> list[AccountResponse]:
        response = self._transport.request(
            "GET",
            "/api/v1/accounts",
            expected_status=200,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return [AccountResponse.model_validate(item) for item in response.json()]

    def list_activity(
        self,
        *,
        access_token: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ActivityPageResponse:
        params: dict[str, str | int] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor

        response = self._transport.request(
            "GET",
            "/api/v1/activity",
            expected_status=200,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        return ActivityPageResponse.model_validate(response.json())

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

    def create_deposit(
        self,
        *,
        destination_account_id: uuid.UUID,
        amount: str,
        access_token: str,
        idempotency_key: str,
    ) -> DepositResponse:
        response = self._transport.request(
            "POST",
            "/api/v1/deposits",
            expected_status=202,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Idempotency-Key": idempotency_key,
            },
            json_body={
                "destination_account_id": str(destination_account_id),
                "amount": amount,
            },
        )
        return DepositResponse.model_validate(response.json())

    def get_deposit(
        self,
        *,
        instruction_id: uuid.UUID,
        access_token: str,
    ) -> DepositResponse:
        response = self._transport.request(
            "GET",
            f"/api/v1/deposits/{instruction_id}",
            expected_status=200,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return DepositResponse.model_validate(response.json())

    def create_withdrawal(
        self,
        *,
        source_account_id: uuid.UUID,
        amount: str,
        access_token: str,
        idempotency_key: str,
    ) -> WithdrawalResponse:
        response = self._transport.request(
            "POST",
            "/api/v1/withdrawals",
            expected_status=202,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Idempotency-Key": idempotency_key,
            },
            json_body={
                "source_account_id": str(source_account_id),
                "amount": amount,
            },
        )
        return WithdrawalResponse.model_validate(response.json())

    def get_withdrawal(
        self,
        *,
        instruction_id: uuid.UUID,
        access_token: str,
    ) -> WithdrawalResponse:
        response = self._transport.request(
            "GET",
            f"/api/v1/withdrawals/{instruction_id}",
            expected_status=200,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return WithdrawalResponse.model_validate(response.json())

    def create_transfer(
        self,
        *,
        source_account_id: uuid.UUID,
        destination_account_id: uuid.UUID,
        amount: str,
        access_token: str,
        idempotency_key: str | None,
    ) -> TransferResponse:
        return self.create_transfer_from_payload(
            payload={
                "source_account_id": str(source_account_id),
                "destination_account_id": str(destination_account_id),
                "amount": amount,
            },
            access_token=access_token,
            idempotency_key=idempotency_key,
        )

    def create_transfer_from_payload(
        self,
        *,
        payload: Mapping[str, object],
        access_token: str,
        idempotency_key: str | None,
    ) -> TransferResponse:
        headers = {"Authorization": f"Bearer {access_token}"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key

        response = self._transport.request(
            "POST",
            "/api/v1/transfers",
            expected_status=201,
            headers=headers,
            json_body=payload,
        )
        return TransferResponse.model_validate(response.json())

    def create_account_transfer(
        self,
        *,
        source_account_id: uuid.UUID,
        destination_account_id: uuid.UUID,
        amount: str,
        access_token: str,
        idempotency_key: str,
        scheduled_for: date | None = None,
    ) -> TransferResponse:
        payload: dict[str, object] = {
            "source_account_id": str(source_account_id),
            "destination_account_id": str(destination_account_id),
            "amount": amount,
        }
        if scheduled_for is not None:
            payload["scheduled_for"] = scheduled_for.isoformat()

        response = self._transport.request(
            "POST",
            "/api/v1/account-transfers",
            expected_status=201,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Idempotency-Key": idempotency_key,
            },
            json_body=payload,
        )
        return TransferResponse.model_validate(response.json())

    def get_transfer(
        self,
        *,
        transfer_id: uuid.UUID,
        access_token: str,
    ) -> TransferResponse:
        response = self._transport.request(
            "GET",
            f"/api/v1/transfers/{transfer_id}",
            expected_status=200,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return TransferResponse.model_validate(response.json())
