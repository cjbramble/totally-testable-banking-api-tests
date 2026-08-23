from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@pytest.mark.contract
@pytest.mark.negative
def test_duplicate_email_registration_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.register_user(
            email=registered_user.email,
            display_name="Another Test User",
            password="Another-test-password",
        )

    error = exc_info.value
    assert error.status_code == 409
    assert error.error is not None
    assert error.error.error.code == "EMAIL_ALREADY_REGISTERED"


@pytest.mark.contract
@pytest.mark.negative
def test_short_registration_password_is_rejected(
    banking_api_client: BankingApiClient,
) -> None:
    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.register_user(
            email=f"api-test-user-{uuid4().hex}@example.com",
            display_name="Test User",
            password="short",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == "VALIDATION_ERROR"
