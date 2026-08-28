"""Registration rejection tests for identity normalization and input validation."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.test_data import RegisteredUser


@pytest.mark.negative
def test_duplicate_email_registration_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
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


@pytest.mark.negative
def test_case_variant_email_registration_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
) -> None:
    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.register_user(
            email=registered_user.email.upper(),
            display_name="Case Variant Test User",
            password="Case-variant-test-password",
        )

    error = exc_info.value
    assert error.status_code == 409
    assert error.error is not None
    assert error.error.error.code == "EMAIL_ALREADY_REGISTERED"


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


@pytest.mark.negative
def test_malformed_registration_email_is_rejected(
    banking_api_client: BankingApiClient,
) -> None:
    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.register_user(
            email=f"api-test-user-{uuid4().hex}",
            display_name="Test User",
            password="Valid-test-password",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == "VALIDATION_ERROR"
