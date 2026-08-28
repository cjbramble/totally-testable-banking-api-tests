"""Activity entry projection across banking operation types."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import ActivityDirection, ActivityKind
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.operation_polling import wait_for_settlement
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserAuthenticator,
    UserRegistrar,
)
from totally_testable_banking_api_tests.test_data import (
    ActivityUserFunder,
    RegisteredUser,
)


@pytest.mark.invariant
def test_transfer_appears_as_sent_and_received_activity(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    sender = authenticate_user(registered_user)
    recipient = authenticate_user(
        register_user(display_name="Recipient Test User"),
    )

    create_settled_deposit(
        destination_account_id=sender.checking.id,
        access_token=sender.access_token,
    )

    transfer = banking_api_client.create_transfer(
        source_account_id=sender.checking.id,
        destination_account_id=recipient.checking.id,
        amount="25.00",
        access_token=sender.access_token,
        idempotency_key=f"transfer-{uuid4()}",
    )

    sender_page = banking_api_client.list_activity(
        access_token=sender.access_token,
    )
    recipient_page = banking_api_client.list_activity(
        access_token=recipient.access_token,
    )
    sender_matches = [item for item in sender_page.items if item.operation_id == transfer.id]
    recipient_matches = [item for item in recipient_page.items if item.operation_id == transfer.id]

    assert len(sender_matches) == 1
    assert len(recipient_matches) == 1
    sender_activity = sender_matches[0]
    recipient_activity = recipient_matches[0]

    assert sender_activity.kind == ActivityKind.TRANSFER
    assert sender_activity.direction == ActivityDirection.SENT
    assert sender_activity.account_id == sender.checking.id
    assert sender_activity.amount == "25.00"
    assert sender_activity.currency == "USD"
    assert sender_activity.status == "POSTED"

    assert recipient_activity.kind == ActivityKind.TRANSFER
    assert recipient_activity.direction == ActivityDirection.RECEIVED
    assert recipient_activity.account_id == recipient.checking.id
    assert recipient_activity.amount == "25.00"
    assert recipient_activity.currency == "USD"
    assert recipient_activity.status == "POSTED"


@pytest.mark.invariant
def test_mixed_activity_cursor_traversal_preserves_identity_and_order(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    fund_activity_user: ActivityUserFunder,
) -> None:
    activity_user = fund_activity_user(registered_user)
    recipient = authenticate_user(
        register_user(display_name="Recipient Test User"),
    )
    transfer = banking_api_client.create_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=recipient.checking.id,
        amount="20.00",
        access_token=activity_user.access_token,
        idempotency_key=f"transfer-{uuid4()}",
    )
    account_transfer = banking_api_client.create_account_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=activity_user.savings.id,
        amount="25.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=activity_user.savings.id,
        amount="10.00",
        access_token=activity_user.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
    )
    wait_for_settlement(
        lambda: banking_api_client.get_withdrawal(
            instruction_id=withdrawal.id,
            access_token=activity_user.access_token,
        ),
        operation_name="activity withdrawal",
    )

    first_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
    )
    cursor = first_page.next_cursor
    assert cursor is not None
    second_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
        cursor=cursor,
    )
    collected_items = [*first_page.items, *second_page.items]

    assert [item.operation_id for item in collected_items] == [
        withdrawal.id,
        account_transfer.id,
        transfer.id,
        activity_user.deposit_id,
    ]
    assert [item.kind for item in collected_items] == [
        ActivityKind.WITHDRAWAL,
        ActivityKind.ACCOUNT_TRANSFER,
        ActivityKind.TRANSFER,
        ActivityKind.DEPOSIT,
    ]
    assert second_page.next_cursor is None
