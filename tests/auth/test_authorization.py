"""Account ownership tests covering valid access and outsider concealment."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


def test_owner_can_retrieve_their_account(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]

    retrieved = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )

    assert retrieved.id == account.id
    assert retrieved.account_type == account.account_type


@pytest.mark.negative
def test_outsider_cannot_retrieve_another_users_account(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    owner_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    owner_account = banking_api_client.list_accounts(
        access_token=owner_token.access_token,
    )[0]

    outsider_id = uuid4().hex
    outsider_email = f"api-test-user-{outsider_id}@example.com"
    outsider_password = f"Test-user-{outsider_id}"
    banking_api_client.register_user(
        email=outsider_email,
        display_name="Outsider Test User",
        password=outsider_password,
    )
    outsider_token = banking_api_client.login(
        email=outsider_email,
        password=outsider_password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.get_account(
            account_id=owner_account.id,
            access_token=outsider_token.access_token,
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "ACCOUNT_NOT_FOUND"
