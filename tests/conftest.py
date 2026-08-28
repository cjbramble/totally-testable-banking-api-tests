"""Function-scoped fixtures for isolated users and API client lifecycle."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    DepositResponse,
    ProductAccountType,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.operation_polling import wait_for_settlement
from totally_testable_banking_api_tests.processor_control import ProcessorControlClient
from totally_testable_banking_api_tests.scheduled_worker_control import ScheduledWorkerControl
from totally_testable_banking_api_tests.settings import load_settings
from totally_testable_banking_api_tests.test_data import FundedAccount, RegisteredUser


class RegisteredUserFactory:
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


class SettledDepositFactory:
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


@pytest.fixture
def banking_api_client() -> Iterator[BankingApiClient]:
    """Provide one cookie-preserving API client and close it after each test."""

    settings = load_settings()
    transport = ApiClient(
        base_url=settings.sut_base_url,
        timeout=settings.request_timeout_seconds,
    )

    try:
        yield BankingApiClient(transport)
    finally:
        transport.close()


@pytest.fixture
def processor_control_client() -> Iterator[ProcessorControlClient]:
    """Provide an isolated client for the local simulated-processor boundary."""

    settings = load_settings()
    transport = ApiClient(
        base_url=settings.processor_control_url,
        timeout=settings.request_timeout_seconds,
    )

    try:
        yield ProcessorControlClient(
            transport,
            token=settings.processor_control_secret.get_secret_value(),
        )
    finally:
        transport.close()


@pytest.fixture
def scheduled_worker_control() -> ScheduledWorkerControl:
    """Provide operation-scoped access to the local scheduled-transfer worker."""

    settings = load_settings()
    return ScheduledWorkerControl(settings.sut_compose_file)


@pytest.fixture
def registered_user_factory(
    banking_api_client: BankingApiClient,
) -> RegisteredUserFactory:
    """Provide a function-scoped factory for isolated registered users."""

    return RegisteredUserFactory(banking_api_client)


@pytest.fixture
def registered_user(
    registered_user_factory: RegisteredUserFactory,
) -> RegisteredUser:
    """Register one uniquely named user through the normal product API."""

    return registered_user_factory()


@pytest.fixture
def create_settled_deposit(
    banking_api_client: BankingApiClient,
) -> SettledDepositFactory:
    """Provide a callable that creates a deposit and waits for settlement."""

    return SettledDepositFactory(banking_api_client)


@pytest.fixture
def funded_account(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    create_settled_deposit: SettledDepositFactory,
) -> FundedAccount:
    """Fund one unique user's checking account through normal product routes."""

    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=token.access_token,
        )
        if account.account_type is ProductAccountType.CHECKING
    )
    create_settled_deposit(
        destination_account_id=account.id,
        access_token=token.access_token,
    )

    funded = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    return FundedAccount(access_token=token.access_token, account=funded)
