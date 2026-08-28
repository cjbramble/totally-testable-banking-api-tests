"""Unit tests for reusable API setup actions."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
    TokenResponse,
    UserResponse,
)
from totally_testable_banking_api_tests.setup_actions import UserAuthenticator
from totally_testable_banking_api_tests.test_data import RegisteredUser

pytestmark = pytest.mark.unit


class _StubAuthenticationClient:
    def __init__(self) -> None:
        self.login_credentials: tuple[str, str] | None = None
        self.account_access_token: str | None = None

    def login(self, *, email: str, password: str) -> TokenResponse:
        self.login_credentials = (email, password)
        return TokenResponse(access_token="access-token", expires_in=1800)

    def list_accounts(self, *, access_token: str) -> list[AccountResponse]:
        self.account_access_token = access_token
        return [
            AccountResponse(
                id=UUID(int=2),
                account_type=ProductAccountType.SAVINGS,
                currency="USD",
                settled_balance="0.00",
                available_balance="0.00",
            ),
            AccountResponse(
                id=UUID(int=1),
                account_type=ProductAccountType.CHECKING,
                currency="USD",
                settled_balance="0.00",
                available_balance="0.00",
            ),
        ]


def test_authenticate_user_logs_in_and_selects_both_accounts() -> None:
    client = _StubAuthenticationClient()
    registered_user = RegisteredUser(
        user=UserResponse(
            id=UUID(int=3),
            email="user@example.com",
            display_name="Test User",
            created_at=datetime(2026, 8, 28, tzinfo=UTC),
        ),
        email="user@example.com",
        password="test-password",
    )

    authenticated = UserAuthenticator(client)(registered_user)

    assert client.login_credentials == ("user@example.com", "test-password")
    assert client.account_access_token == "access-token"
    assert authenticated.registered_user is registered_user
    assert authenticated.access_token == "access-token"
    assert authenticated.checking.id == UUID(int=1)
    assert authenticated.savings.id == UUID(int=2)
