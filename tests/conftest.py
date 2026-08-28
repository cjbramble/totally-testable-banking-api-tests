"""Function-scoped fixtures for isolated users and API client lifecycle."""

from collections.abc import Iterator

import pytest

from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.factories import (
    RegisteredUserFactory,
    SettledDepositFactory,
)
from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.processor_control import ProcessorControlClient
from totally_testable_banking_api_tests.scheduled_worker_control import ScheduledWorkerControl
from totally_testable_banking_api_tests.settings import load_settings
from totally_testable_banking_api_tests.test_data import FundedAccount, RegisteredUser


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
