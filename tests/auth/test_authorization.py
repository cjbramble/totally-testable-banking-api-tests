"""Account ownership tests covering valid access and outsider concealment."""

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.setup_actions import UserAuthenticator, UserRegistrar
from totally_testable_banking_api_tests.test_data import RegisteredUser


def test_owner_can_retrieve_their_account(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
) -> None:
    authenticated = authenticate_user(registered_user)

    retrieved = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )

    assert retrieved.id == authenticated.checking.id
    assert retrieved.account_type == authenticated.checking.account_type


@pytest.mark.negative
def test_outsider_cannot_retrieve_another_users_account(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
) -> None:
    owner = authenticate_user(registered_user)

    outsider = register_user(display_name="Outsider Test User")
    outsider_token = banking_api_client.login(
        email=outsider.email,
        password=outsider.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.get_account(
            account_id=owner.checking.id,
            access_token=outsider_token.access_token,
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error_code == "ACCOUNT_NOT_FOUND"
