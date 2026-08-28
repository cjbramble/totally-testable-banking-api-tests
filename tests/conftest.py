"""Function-scoped fixtures for isolated users and API client lifecycle."""

from collections.abc import Iterator

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.settings import load_settings
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserAuthenticator,
    UserRegistrar,
)
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
def register_user(
    banking_api_client: BankingApiClient,
) -> UserRegistrar:
    """Provide a callable that registers isolated users through the API."""

    return UserRegistrar(banking_api_client)


@pytest.fixture
def registered_user(
    register_user: UserRegistrar,
) -> RegisteredUser:
    """Register one uniquely named user through the normal product API."""

    return register_user()


@pytest.fixture
def authenticate_user(
    banking_api_client: BankingApiClient,
) -> UserAuthenticator:
    """Provide a callable that authenticates a registered user and loads their accounts."""

    return UserAuthenticator(banking_api_client)


@pytest.fixture
def create_settled_deposit(
    banking_api_client: BankingApiClient,
) -> SettledDepositCreator:
    """Provide a callable that creates a deposit and waits for settlement."""

    return SettledDepositCreator(banking_api_client)


@pytest.fixture
def funded_account(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> FundedAccount:
    """Fund one unique user's checking account through normal product routes."""

    authenticated = authenticate_user(registered_user)
    create_settled_deposit(
        destination_account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )

    funded = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    return FundedAccount(access_token=authenticated.access_token, account=funded)
