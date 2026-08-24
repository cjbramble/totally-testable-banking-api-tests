import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@pytest.mark.contract
def test_browser_session_cookie_supports_session_read(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    created = banking_api_client.create_browser_session(
        email=registered_user.email,
        password=registered_user.password,
    )

    current = banking_api_client.read_browser_session()

    assert created.expires_in > 0
    assert current.id == registered_user.user.id
    assert current.email == registered_user.user.email


@pytest.mark.contract
@pytest.mark.negative
def test_deleted_browser_session_is_no_longer_authenticated(
    banking_api_client: BankingApiClient,
    registered_user,
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
    assert error.error is not None
    assert error.error.error.code == "AUTHENTICATION_REQUIRED"
