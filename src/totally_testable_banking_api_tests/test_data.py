"""Typed data shared by API test fixtures and test functions."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from totally_testable_banking_api_tests.api_models import AccountResponse, UserResponse


@dataclass(frozen=True)
class RegisteredUser:
    """Immutable registration result plus credentials needed by later actions."""

    user: UserResponse
    email: str
    password: str


@dataclass(frozen=True)
class AuthenticatedUser:
    """Registered user with a bearer token and both product accounts."""

    user: UserResponse
    access_token: str
    checking: AccountResponse
    savings: AccountResponse


@dataclass(frozen=True)
class FundedAccount:
    """Authenticated checking account whose funding deposit has settled."""

    access_token: str
    account: AccountResponse


@dataclass(frozen=True)
class FundedActivityUser:
    """Authenticated user with funded accounts and the funding operation identity."""

    access_token: str
    checking: AccountResponse
    savings: AccountResponse
    deposit_id: UUID


type ActivityUserFunder = Callable[[RegisteredUser], FundedActivityUser]
