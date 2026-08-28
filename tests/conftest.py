"""Function-scoped fixtures for isolated users and API client lifecycle."""

from collections.abc import Iterator

import pytest

from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.settings import load_settings
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
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
def create_settled_deposit(
    banking_api_client: BankingApiClient,
) -> SettledDepositCreator:
    """Provide a callable that creates a deposit and waits for settlement."""

    return SettledDepositCreator(banking_api_client)


@pytest.fixture
def funded_account(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    create_settled_deposit: SettledDepositCreator,
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
