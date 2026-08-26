"""Bearer-authentication rejection tests using independently registered users."""

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@pytest.mark.negative
def test_invalid_password_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user,
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
