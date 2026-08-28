"""Typed data shared by API test fixtures and test functions."""

from dataclasses import dataclass

from totally_testable_banking_api_tests.api_models import AccountResponse, UserResponse


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
