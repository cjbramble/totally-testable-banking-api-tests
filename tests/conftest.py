"""Function-scoped fixtures for isolated users and API client lifecycle."""

import time
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
    UserResponse,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.settings import load_settings


@dataclass(frozen=True)
class RegisteredUser:
    """Immutable registration result plus credentials needed by later actions."""

    user: UserResponse
    email: str
    password: str


@dataclass(frozen=True)
class FundedAccount:
    """Authenticated checking account whose funding deposit has settled."""

    access_token: str
    account: AccountResponse


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
def registered_user(banking_api_client: BankingApiClient) -> RegisteredUser:
    """Register a uniquely named user through the normal product API."""

    unique_id = uuid4().hex
    email = f"api-test-user-{unique_id}@example.com"
    password = f"Test-user-{unique_id}"
    user = banking_api_client.register_user(
        email=email,
        display_name="Test User",
        password=password,
    )
    return RegisteredUser(user=user, email=email, password=password)


@pytest.fixture
def funded_account(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
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
    deposit = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    deadline = time.monotonic() + 10.0

    while True:
        current = banking_api_client.get_deposit(
            instruction_id=deposit.id,
            access_token=token.access_token,
        )
        if current.status == "SETTLED":
            break
        if current.status == "FAILED":
            pytest.fail(f"Funding deposit failed with {current.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(f"Funding deposit did not settle; final status was {current.status!r}")
        time.sleep(0.1)

    funded = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    return FundedAccount(access_token=token.access_token, account=funded)
