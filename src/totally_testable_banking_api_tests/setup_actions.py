"""Reusable setup actions performed through the banking API."""

from uuid import UUID, uuid4

from totally_testable_banking_api_tests.api_models import DepositResponse
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.operation_polling import wait_for_settlement
from totally_testable_banking_api_tests.test_data import RegisteredUser


class UserRegistrar:
    """Create isolated registered users through the normal product API."""

    def __init__(self, banking_api_client: BankingApiClient) -> None:
        self._banking_api_client = banking_api_client

    def __call__(self, *, display_name: str = "Test User") -> RegisteredUser:
        unique_id = uuid4().hex
        email = f"api-test-user-{unique_id}@example.com"
        password = f"Test-user-{unique_id}"
        user = self._banking_api_client.register_user(
            email=email,
            display_name=display_name,
            password=password,
        )
        return RegisteredUser(user=user, email=email, password=password)


class SettledDepositCreator:
    """Create deposits through the product API and await settlement."""

    def __init__(self, banking_api_client: BankingApiClient) -> None:
        self._banking_api_client = banking_api_client

    def __call__(
        self,
        *,
        destination_account_id: UUID,
        access_token: str,
        amount: str = "100.00",
        idempotency_key: str | None = None,
    ) -> DepositResponse:
        key = idempotency_key if idempotency_key is not None else f"deposit-{uuid4()}"
        deposit = self._banking_api_client.create_deposit(
            destination_account_id=destination_account_id,
            amount=amount,
            access_token=access_token,
            idempotency_key=key,
        )
        return wait_for_settlement(
            lambda: self._banking_api_client.get_deposit(
                instruction_id=deposit.id,
                access_token=access_token,
            ),
            operation_name="funding deposit",
        )
