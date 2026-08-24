import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient


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
