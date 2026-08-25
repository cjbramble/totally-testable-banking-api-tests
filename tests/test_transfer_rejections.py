from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@pytest.mark.contract
@pytest.mark.negative
@pytest.mark.parametrize(
    ("amount", "expected_error_code"),
    [
        pytest.param("0.00", "INVALID_AMOUNT", id="zero"),
        pytest.param("-1.00", "INVALID_AMOUNT", id="negative"),
        pytest.param("1.001", "INVALID_AMOUNT", id="over-precision"),
        pytest.param(
            "100000000000000000000.00",
            "VALIDATION_ERROR",
            id="oversized",
        ),
    ],
)
def test_invalid_amount_transfer_is_rejected_without_balance_effect(
    banking_api_client: BankingApiClient,
    registered_user,
    amount: str,
    expected_error_code: str,
) -> None:
    sender_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    sender_account = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]

    recipient_id = uuid4().hex
    recipient_email = f"api-test-user-{recipient_id}@example.com"
    recipient_password = f"Test-user-{recipient_id}"
    banking_api_client.register_user(
        email=recipient_email,
        display_name="Recipient Test User",
        password=recipient_password,
    )
    recipient_token = banking_api_client.login(
        email=recipient_email,
        password=recipient_password,
    )
    recipient_account = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]

    sender_before = (sender_account.settled_balance, sender_account.available_balance)
    recipient_before = (
        recipient_account.settled_balance,
        recipient_account.available_balance,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender_account.id,
            destination_account_id=recipient_account.id,
            amount=amount,
            access_token=sender_token.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == expected_error_code

    sender_after = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]
    recipient_after = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]
    assert (sender_after.settled_balance, sender_after.available_balance) == sender_before
    assert (
        recipient_after.settled_balance,
        recipient_after.available_balance,
    ) == recipient_before


@pytest.mark.contract
@pytest.mark.negative
@pytest.mark.parametrize(
    ("idempotency_key", "expected_error_code"),
    [
        pytest.param(None, "IDEMPOTENCY_KEY_REQUIRED", id="missing"),
        pytest.param("", "IDEMPOTENCY_KEY_INVALID", id="empty"),
        pytest.param("transfer key", "IDEMPOTENCY_KEY_INVALID", id="malformed"),
    ],
)
def test_invalid_idempotency_key_is_rejected_without_balance_effect(
    banking_api_client: BankingApiClient,
    registered_user,
    idempotency_key: str | None,
    expected_error_code: str,
) -> None:
    sender_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    sender_account = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]

    recipient_id = uuid4().hex
    recipient_email = f"api-test-user-{recipient_id}@example.com"
    recipient_password = f"Test-user-{recipient_id}"
    banking_api_client.register_user(
        email=recipient_email,
        display_name="Recipient Test User",
        password=recipient_password,
    )
    recipient_token = banking_api_client.login(
        email=recipient_email,
        password=recipient_password,
    )
    recipient_account = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]

    sender_before = (sender_account.settled_balance, sender_account.available_balance)
    recipient_before = (
        recipient_account.settled_balance,
        recipient_account.available_balance,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender_account.id,
            destination_account_id=recipient_account.id,
            amount="1.00",
            access_token=sender_token.access_token,
            idempotency_key=idempotency_key,
        )

    error = exc_info.value
    assert error.status_code == 400
    assert error.error is not None
    assert error.error.error.code == expected_error_code

    sender_after = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]
    recipient_after = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]
    assert (sender_after.settled_balance, sender_after.available_balance) == sender_before
    assert (
        recipient_after.settled_balance,
        recipient_after.available_balance,
    ) == recipient_before
