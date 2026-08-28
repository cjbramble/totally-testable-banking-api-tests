"""P2P transfer request-shape and field validation behavior."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.account_selection import get_account_by_type
from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserAuthenticator,
    UserRegistrar,
)
from totally_testable_banking_api_tests.test_data import RegisteredUser


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
def test_invalid_amount_transfer_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    amount: str,
    expected_error_code: str,
) -> None:
    sender = authenticate_user(registered_user)
    recipient = authenticate_user(
        register_user(display_name="Recipient Test User"),
    )

    sender_before = (sender.checking.settled_balance, sender.checking.available_balance)
    recipient_before = (
        recipient.checking.settled_balance,
        recipient.checking.available_balance,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=recipient.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender.checking.id,
            destination_account_id=recipient.checking.id,
            amount=amount,
            access_token=sender.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error_code == expected_error_code

    sender_after = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=sender.access_token,
        ),
        ProductAccountType.CHECKING,
    )
    recipient_after = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=recipient.access_token,
        ),
        ProductAccountType.CHECKING,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=recipient.access_token,
    ).items
    assert (sender_after.settled_balance, sender_after.available_balance) == sender_before
    assert (
        recipient_after.settled_balance,
        recipient_after.available_balance,
    ) == recipient_before
    assert sender_activity_after == sender_activity_before
    assert recipient_activity_after == recipient_activity_before


@pytest.mark.negative
@pytest.mark.parametrize(
    ("idempotency_key", "expected_error_code"),
    [
        pytest.param(None, "IDEMPOTENCY_KEY_REQUIRED", id="missing"),
        pytest.param("", "IDEMPOTENCY_KEY_INVALID", id="empty"),
        pytest.param("transfer key", "IDEMPOTENCY_KEY_INVALID", id="malformed"),
        pytest.param("k" * 129, "IDEMPOTENCY_KEY_INVALID", id="oversized"),
    ],
)
def test_invalid_idempotency_key_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    idempotency_key: str | None,
    expected_error_code: str,
) -> None:
    sender = authenticate_user(registered_user)
    recipient = authenticate_user(
        register_user(display_name="Recipient Test User"),
    )

    sender_before = (sender.checking.settled_balance, sender.checking.available_balance)
    recipient_before = (
        recipient.checking.settled_balance,
        recipient.checking.available_balance,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=recipient.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender.checking.id,
            destination_account_id=recipient.checking.id,
            amount="1.00",
            access_token=sender.access_token,
            idempotency_key=idempotency_key,
        )

    error = exc_info.value
    assert error.status_code == 400
    assert error.error_code == expected_error_code

    sender_after = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=sender.access_token,
        ),
        ProductAccountType.CHECKING,
    )
    recipient_after = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=recipient.access_token,
        ),
        ProductAccountType.CHECKING,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=recipient.access_token,
    ).items
    assert (sender_after.settled_balance, sender_after.available_balance) == sender_before
    assert (
        recipient_after.settled_balance,
        recipient_after.available_balance,
    ) == recipient_before
    assert sender_activity_after == sender_activity_before
    assert recipient_activity_after == recipient_activity_before


@pytest.mark.negative
def test_transfer_missing_destination_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    sender = authenticate_user(registered_user)
    create_settled_deposit(
        destination_account_id=sender.checking.id,
        access_token=sender.access_token,
    )

    source_before = banking_api_client.get_account(
        account_id=sender.checking.id,
        access_token=sender.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer_from_payload(
            payload={
                "source_account_id": str(sender.checking.id),
                "amount": "25.00",
            },
            access_token=sender.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error_code == "VALIDATION_ERROR"

    source_after = banking_api_client.get_account(
        account_id=sender.checking.id,
        access_token=sender.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items

    assert (
        source_after.settled_balance,
        source_after.available_balance,
    ) == (
        source_before.settled_balance,
        source_before.available_balance,
    )
    assert activity_after == activity_before
