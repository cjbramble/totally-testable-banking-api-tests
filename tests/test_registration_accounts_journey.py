import pytest

from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.smoke
def test_registered_user_can_authenticate_and_list_empty_accounts(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    accounts = banking_api_client.list_accounts(access_token=token.access_token)

    assert registered_user.user.email == registered_user.email
    assert registered_user.user.display_name == "Test User"

    accounts_by_type = {account.account_type: account for account in accounts}
    assert set(accounts_by_type) == {
        ProductAccountType.CHECKING,
        ProductAccountType.SAVINGS,
    }
    for account in accounts:
        assert account.currency == "USD"
        assert account.settled_balance == "0.00"
        assert account.available_balance == "0.00"
