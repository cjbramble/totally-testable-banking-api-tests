"""Login and bearer-authentication rejection tests."""

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import (
    ApiClient,
    UnexpectedStatusError,
)
from totally_testable_banking_api_tests.settings import load_settings
from totally_testable_banking_api_tests.test_data import RegisteredUser


@pytest.mark.negative
def test_invalid_password_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
) -> None:
    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.login(
            email=registered_user.email,
            password="wrong-password-for-test",
        )

    error = exc_info.value
    assert error.status_code == 401
    assert error.error is not None
    assert error.error.error.code == "INVALID_CREDENTIALS"


@pytest.mark.negative
def test_missing_bearer_credentials_are_rejected() -> None:
    settings = load_settings()
    client = ApiClient(
        base_url=settings.sut_base_url,
        timeout=settings.request_timeout_seconds,
    )

    try:
        with pytest.raises(UnexpectedStatusError) as exc_info:
            client.request("GET", "/api/v1/accounts", expected_status=200)
    finally:
        client.close()

    error = exc_info.value
    assert error.status_code == 401
    assert error.error is not None
    assert error.error.error.code == "AUTHENTICATION_REQUIRED"
    assert error.error.error.message


@pytest.mark.negative
def test_invalid_bearer_token_is_rejected(
    banking_api_client: BankingApiClient,
) -> None:
    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.list_accounts(access_token="invalid-token-for-test")

    error = exc_info.value
    assert error.status_code == 401
    assert error.error is not None
    assert error.error.error.code == "AUTHENTICATION_REQUIRED"
