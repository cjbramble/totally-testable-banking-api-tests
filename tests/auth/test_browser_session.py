"""Cookie-session and CSRF security tests at the HTTP API boundary."""

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.test_data import RegisteredUser


def test_browser_session_persists_cookie_for_session_read(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
) -> None:
    created = banking_api_client.create_browser_session(
        email=registered_user.email,
        password=registered_user.password,
    )

    current = banking_api_client.read_browser_session()

    assert created.expires_in > 0
    assert current.id == registered_user.user.id
    assert current.email == registered_user.user.email


@pytest.mark.negative
def test_logout_invalidates_browser_session(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
) -> None:
    banking_api_client.create_browser_session(
        email=registered_user.email,
        password=registered_user.password,
    )
    banking_api_client.delete_browser_session()

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.read_browser_session()

    error = exc_info.value
    assert error.status_code == 401
    assert error.error_code == "AUTHENTICATION_REQUIRED"


@pytest.mark.negative
def test_invalid_csrf_token_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
) -> None:
    banking_api_client.create_browser_session(
        email=registered_user.email,
        password=registered_user.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.delete_browser_session(csrf_token="invalid-csrf-token")

    error = exc_info.value
    assert error.status_code == 403
    assert error.error_code == "CSRF_VALIDATION_FAILED"
