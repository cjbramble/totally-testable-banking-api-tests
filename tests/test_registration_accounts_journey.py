import uuid

import pytest

from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.settings import load_settings


@pytest.mark.smoke
def test_registered_user_can_authenticate_and_list_empty_accounts() -> None:
    settings = load_settings()
    transport = ApiClient(
        base_url=settings.sut_base_url,
        timeout=settings.request_timeout_seconds,
    )
    banking = BankingApiClient(transport)
    unique_id = uuid.uuid4().hex
    email = f"api-test-user-{unique_id}@example.com"
    password = f"Test-user-{unique_id}"

    try:
        registered_user = banking.register_user(
            email=email,
            display_name="Test User",
            password=password,
        )
        token = banking.login(email=email, password=password)
        accounts = banking.list_accounts(access_token=token.access_token)
    finally:
        transport.close()

    assert registered_user.email == email
    assert registered_user.display_name == "Test User"

    accounts_by_type = {account.account_type: account for account in accounts}
    assert set(accounts_by_type) == {
        ProductAccountType.CHECKING,
        ProductAccountType.SAVINGS,
    }
    for account in accounts:
        assert account.currency == "USD"
        assert account.settled_balance == "0.00"
        assert account.available_balance == "0.00"
