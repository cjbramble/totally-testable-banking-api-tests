"""Transfer idempotency-key scope across users and operation types."""

from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
)
from totally_testable_banking_api_tests.test_data import FundedTransferContext


@pytest.mark.invariant
def test_two_users_can_use_the_same_idempotency_key_independently(
    banking_api_client: BankingApiClient,
    funded_transfer_context: FundedTransferContext,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    context = funded_transfer_context
    create_settled_deposit(
        destination_account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )

    source_before = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    shared_key = f"shared-transfer-{uuid4()}"
    sender_transfer = banking_api_client.create_transfer(
        source_account_id=context.source_account.id,
        destination_account_id=context.destination_account.id,
        amount="10.00",
        access_token=context.sender_access_token,
        idempotency_key=shared_key,
    )
    recipient_transfer = banking_api_client.create_transfer(
        source_account_id=context.destination_account.id,
        destination_account_id=context.source_account.id,
        amount="15.00",
        access_token=context.recipient_access_token,
        idempotency_key=shared_key,
    )

    source_after = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    assert sender_transfer.id != recipient_transfer.id
    assert Decimal(source_after.settled_balance) == (
        Decimal(source_before.settled_balance) - Decimal("10.00") + Decimal("15.00")
    )
    assert Decimal(source_after.available_balance) == (
        Decimal(source_before.available_balance) - Decimal("10.00") + Decimal("15.00")
    )
    assert Decimal(destination_after.settled_balance) == (
        Decimal(destination_before.settled_balance) + Decimal("10.00") - Decimal("15.00")
    )
    assert Decimal(destination_after.available_balance) == (
        Decimal(destination_before.available_balance) + Decimal("10.00") - Decimal("15.00")
    )
    assert len(sender_activity_after) == len(sender_activity_before) + 2
    assert len(recipient_activity_after) == len(recipient_activity_before) + 2
    for operation_id in (sender_transfer.id, recipient_transfer.id):
        assert sum(item.operation_id == operation_id for item in sender_activity_after) == 1
        assert sum(item.operation_id == operation_id for item in recipient_activity_after) == 1


@pytest.mark.invariant
def test_same_key_is_independent_across_deposit_and_transfer_operations(
    banking_api_client: BankingApiClient,
    funded_transfer_context: FundedTransferContext,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    context = funded_transfer_context
    source_before = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    shared_key = f"cross-operation-{uuid4()}"
    deposit = create_settled_deposit(
        destination_account_id=context.source_account.id,
        access_token=context.sender_access_token,
        amount="100.00",
        idempotency_key=shared_key,
    )
    transfer = banking_api_client.create_transfer(
        source_account_id=context.source_account.id,
        destination_account_id=context.destination_account.id,
        amount="25.00",
        access_token=context.sender_access_token,
        idempotency_key=shared_key,
    )

    source_after = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    assert deposit.id != transfer.id
    assert Decimal(source_after.settled_balance) == (
        Decimal(source_before.settled_balance) + Decimal("100.00") - Decimal("25.00")
    )
    assert Decimal(source_after.available_balance) == (
        Decimal(source_before.available_balance) + Decimal("100.00") - Decimal("25.00")
    )
    assert Decimal(destination_after.settled_balance) == (
        Decimal(destination_before.settled_balance) + Decimal("25.00")
    )
    assert Decimal(destination_after.available_balance) == (
        Decimal(destination_before.available_balance) + Decimal("25.00")
    )
    assert len(sender_activity_after) == len(sender_activity_before) + 2
    assert len(recipient_activity_after) == len(recipient_activity_before) + 1
    assert sum(item.operation_id == deposit.id for item in sender_activity_after) == 1
    assert sum(item.operation_id == transfer.id for item in sender_activity_after) == 1
    assert all(item.operation_id != deposit.id for item in recipient_activity_after)
    assert sum(item.operation_id == transfer.id for item in recipient_activity_after) == 1
