"""Controlled races with durable financial postconditions."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    ProductAccountType,
    TransferResponse,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.concurrency
@pytest.mark.invariant
def test_concurrent_same_key_account_transfers_have_one_financial_effect(
    banking_api_client: BankingApiClient,
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
    idempotency_key = f"concurrent-account-transfer-{uuid4()}"
    release = Barrier(3)

    def submit_transfer() -> TransferResponse:
        release.wait(timeout=5.0)
        return banking_api_client.create_account_transfer(
            source_account_id=checking_before.id,
            destination_account_id=savings_before.id,
            amount=str(transfer_amount),
            access_token=funded_account.access_token,
            idempotency_key=idempotency_key,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit_transfer) for _ in range(2)]
        release.wait(timeout=5.0)
        results = [future.result(timeout=10.0) for future in futures]

    checking_after = banking_api_client.get_account(
        account_id=checking_before.id,
        access_token=funded_account.access_token,
    )
    savings_after = banking_api_client.get_account(
        account_id=savings_before.id,
        access_token=funded_account.access_token,
    )
    activity = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    operation_ids = {result.id for result in results}
    matching_activity = [item for item in activity.items if item.operation_id in operation_ids]

    assert len(operation_ids) == 1
    assert all(result.status == "POSTED" for result in results)
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
    assert len(matching_activity) == 1
    assert matching_activity[0].status == "POSTED"
