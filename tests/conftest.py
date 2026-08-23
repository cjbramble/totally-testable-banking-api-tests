from collections.abc import Iterator
from dataclasses import dataclass
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import UserResponse
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.settings import load_settings


@dataclass(frozen=True)
class RegisteredUser:
    user: UserResponse
    email: str
    password: str


@pytest.fixture
def banking_api_client() -> Iterator[BankingApiClient]:
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
    unique_id = uuid4().hex
    email = f"api-test-user-{unique_id}@example.com"
    password = f"Test-user-{unique_id}"
    user = banking_api_client.register_user(
        email=email,
        display_name="Test User",
        password=password,
    )
    return RegisteredUser(user=user, email=email, password=password)
