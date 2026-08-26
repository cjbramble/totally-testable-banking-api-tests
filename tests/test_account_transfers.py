"""Live own-account transfer lifecycle and financial-invariant tests."""

from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.invariant
def test_immediate_checking_to_savings_transfer_moves_exact_amount(
    banking_api_client: BankingApiClient,
    registered_user,
    funded_account,
) -> None:
    savings_before = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=funded_account.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    transfer_amount = Decimal("25.00")

    transfer = banking_api_client.create_account_transfer(
        source_account_id=checking_before.id,
        destination_account_id=savings_before.id,
        amount=str(transfer_amount),
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )

    checking_after = banking_api_client.get_account(
        account_id=checking_before.id,
        access_token=funded_account.access_token,
    )
    savings_after = banking_api_client.get_account(
        account_id=savings_before.id,
        access_token=funded_account.access_token,
    )

    assert transfer.sender_user_id == registered_user.user.id
    assert transfer.recipient_user_id == registered_user.user.id
    assert transfer.source_account_id == checking_before.id
    assert transfer.destination_account_id == savings_before.id
    assert transfer.amount == "25.00"
    assert transfer.currency == "USD"
    assert transfer.status == "POSTED"
    assert transfer.transfer_kind == "OWN_ACCOUNT"
    assert transfer.scheduled_for is None
    assert transfer.completed_at is not None
    assert Decimal(checking_after.settled_balance) == (
        Decimal(checking_before.settled_balance) - transfer_amount
    )
    assert Decimal(checking_after.available_balance) == (
        Decimal(checking_before.available_balance) - transfer_amount
    )
    assert Decimal(savings_after.settled_balance) == (
        Decimal(savings_before.settled_balance) + transfer_amount
    )
    assert Decimal(savings_after.available_balance) == (
        Decimal(savings_before.available_balance) + transfer_amount
    )
