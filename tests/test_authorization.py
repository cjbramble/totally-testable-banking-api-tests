import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@pytest.mark.contract
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
