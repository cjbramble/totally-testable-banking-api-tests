"""Controlled races with durable financial postconditions."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
    TransferResponse,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@dataclass(frozen=True)
class _AuthenticatedCheckingAccount:
    access_token: str
    account: AccountResponse


def _register_checking_account(
    banking_api_client: BankingApiClient,
) -> _AuthenticatedCheckingAccount:
    unique_id = uuid4().hex
    email = f"api-test-user-{unique_id}@example.com"
    password = f"Test-user-{unique_id}"
    banking_api_client.register_user(
        email=email,
        display_name="Recipient Test User",
        password=password,
    )
    token = banking_api_client.login(email=email, password=password)
    account = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=token.access_token,
        )
        if account.account_type is ProductAccountType.CHECKING
    )
    return _AuthenticatedCheckingAccount(
        access_token=token.access_token,
        account=account,
    )


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


@pytest.mark.concurrency
@pytest.mark.invariant
def test_competing_transfers_cannot_overspend_one_account(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    recipients = [
        _register_checking_account(banking_api_client),
        _register_checking_account(banking_api_client),
    ]
    sender_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    transfer_amount = Decimal("75.00")
    release = Barrier(3)

    def submit_transfer(
        destination_account_id: UUID,
        idempotency_key: str,
    ) -> TransferResponse | UnexpectedStatusError:
        release.wait(timeout=5.0)
        try:
            return banking_api_client.create_transfer(
                source_account_id=sender_before.id,
                destination_account_id=destination_account_id,
                amount=str(transfer_amount),
                access_token=funded_account.access_token,
                idempotency_key=idempotency_key,
            )
        except UnexpectedStatusError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                submit_transfer,
                recipient.account.id,
                f"competing-transfer-{uuid4()}",
            )
            for recipient in recipients
        ]
        release.wait(timeout=5.0)
        outcomes = [future.result(timeout=10.0) for future in futures]

    posted = [outcome for outcome in outcomes if isinstance(outcome, TransferResponse)]
    rejected = [outcome for outcome in outcomes if isinstance(outcome, UnexpectedStatusError)]
    sender_after = banking_api_client.get_account(
        account_id=sender_before.id,
        access_token=funded_account.access_token,
    )
    recipient_accounts_after = [
        banking_api_client.get_account(
            account_id=recipient.account.id,
            access_token=recipient.access_token,
        )
        for recipient in recipients
    ]
    activity_after = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    activity_before_ids = {item.operation_id for item in activity_before.items}
    new_activity = [
        item for item in activity_after.items if item.operation_id not in activity_before_ids
    ]

    assert len(posted) == 1
    assert posted[0].status == "POSTED"
    assert len(rejected) == 1
    assert rejected[0].status_code == 409
    assert rejected[0].error is not None
    assert rejected[0].error.error.code == "INSUFFICIENT_FUNDS"
    assert Decimal(sender_after.settled_balance) == (
        Decimal(sender_before.settled_balance) - transfer_amount
    )
    assert Decimal(sender_after.available_balance) == (
        Decimal(sender_before.available_balance) - transfer_amount
    )

    for account_before, account_after in zip(
        (recipient.account for recipient in recipients),
        recipient_accounts_after,
        strict=True,
    ):
        expected_credit = (
            transfer_amount
            if account_before.id == posted[0].destination_account_id
            else Decimal("0.00")
        )
        assert Decimal(account_after.settled_balance) == (
            Decimal(account_before.settled_balance) + expected_credit
        )
        assert Decimal(account_after.available_balance) == (
            Decimal(account_before.available_balance) + expected_credit
        )

    assert len(new_activity) == 1
    assert new_activity[0].operation_id == posted[0].id
    assert new_activity[0].status == "POSTED"
