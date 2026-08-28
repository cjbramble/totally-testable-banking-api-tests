"""Controlled transfer races with durable financial postconditions."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from totally_testable_banking_api_tests.account_selection import get_account_by_type
from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ActivityDirection,
    ProductAccountType,
    TransferResponse,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserRegistrar,
)
from totally_testable_banking_api_tests.test_data import FundedAccount


@dataclass(frozen=True)
class _AuthenticatedCheckingAccount:
    access_token: str
    account: AccountResponse


def _register_checking_account(
    banking_api_client: BankingApiClient,
    register_user: UserRegistrar,
) -> _AuthenticatedCheckingAccount:
    user = register_user(display_name="Recipient Test User")
    token = banking_api_client.login(email=user.email, password=user.password)
    account = get_account_by_type(
        banking_api_client.list_accounts(access_token=token.access_token),
        ProductAccountType.CHECKING,
    )
    return _AuthenticatedCheckingAccount(
        access_token=token.access_token,
        account=account,
    )


def _fund_checking_account(
    banking_api_client: BankingApiClient,
    create_settled_deposit: SettledDepositCreator,
    account: _AuthenticatedCheckingAccount,
    *,
    amount: str,
) -> _AuthenticatedCheckingAccount:
    create_settled_deposit(
        destination_account_id=account.account.id,
        amount=amount,
        access_token=account.access_token,
    )

    return _AuthenticatedCheckingAccount(
        access_token=account.access_token,
        account=banking_api_client.get_account(
            account_id=account.account.id,
            access_token=account.access_token,
        ),
    )


@pytest.mark.concurrency
@pytest.mark.invariant
def test_concurrent_same_key_account_transfers_have_one_financial_effect(
    banking_api_client: BankingApiClient,
    funded_account: FundedAccount,
) -> None:
    savings_before = get_account_by_type(
        banking_api_client.list_accounts(access_token=funded_account.access_token),
        ProductAccountType.SAVINGS,
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
    funded_account: FundedAccount,
    register_user: UserRegistrar,
) -> None:
    recipients = [
        _register_checking_account(banking_api_client, register_user),
        _register_checking_account(banking_api_client, register_user),
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
    assert rejected[0].error_code == "INSUFFICIENT_FUNDS"
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


@pytest.mark.concurrency
@pytest.mark.invariant
def test_opposing_direction_transfers_both_post_with_coherent_balances(
    banking_api_client: BankingApiClient,
    funded_account: FundedAccount,
    register_user: UserRegistrar,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    account_a = _AuthenticatedCheckingAccount(
        access_token=funded_account.access_token,
        account=funded_account.account,
    )
    account_b = _fund_checking_account(
        banking_api_client,
        create_settled_deposit,
        _register_checking_account(banking_api_client, register_user),
        amount="100.00",
    )
    activity_a_before = banking_api_client.list_activity(
        access_token=account_a.access_token,
        limit=100,
    )
    activity_b_before = banking_api_client.list_activity(
        access_token=account_b.access_token,
        limit=100,
    )
    amount_a_to_b = Decimal("30.00")
    amount_b_to_a = Decimal("20.00")
    release = Barrier(3)

    def submit_transfer(
        source: _AuthenticatedCheckingAccount,
        destination: _AuthenticatedCheckingAccount,
        amount: Decimal,
    ) -> TransferResponse:
        release.wait(timeout=5.0)
        return banking_api_client.create_transfer(
            source_account_id=source.account.id,
            destination_account_id=destination.account.id,
            amount=str(amount),
            access_token=source.access_token,
            idempotency_key=f"opposing-transfer-{uuid4()}",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(submit_transfer, account_a, account_b, amount_a_to_b),
            executor.submit(submit_transfer, account_b, account_a, amount_b_to_a),
        ]
        release.wait(timeout=5.0)
        results = [future.result(timeout=10.0) for future in futures]

    account_a_after = banking_api_client.get_account(
        account_id=account_a.account.id,
        access_token=account_a.access_token,
    )
    account_b_after = banking_api_client.get_account(
        account_id=account_b.account.id,
        access_token=account_b.access_token,
    )
    activity_a_after = banking_api_client.list_activity(
        access_token=account_a.access_token,
        limit=100,
    )
    activity_b_after = banking_api_client.list_activity(
        access_token=account_b.access_token,
        limit=100,
    )
    operation_ids = {result.id for result in results}
    activity_a_before_ids = {item.operation_id for item in activity_a_before.items}
    activity_b_before_ids = {item.operation_id for item in activity_b_before.items}
    new_activity_a = [
        item for item in activity_a_after.items if item.operation_id not in activity_a_before_ids
    ]
    new_activity_b = [
        item for item in activity_b_after.items if item.operation_id not in activity_b_before_ids
    ]

    assert len(operation_ids) == 2
    assert all(result.status == "POSTED" for result in results)
    assert Decimal(account_a_after.settled_balance) == (
        Decimal(account_a.account.settled_balance) - amount_a_to_b + amount_b_to_a
    )
    assert Decimal(account_a_after.available_balance) == (
        Decimal(account_a.account.available_balance) - amount_a_to_b + amount_b_to_a
    )
    assert Decimal(account_b_after.settled_balance) == (
        Decimal(account_b.account.settled_balance) - amount_b_to_a + amount_a_to_b
    )
    assert Decimal(account_b_after.available_balance) == (
        Decimal(account_b.account.available_balance) - amount_b_to_a + amount_a_to_b
    )
    assert {item.operation_id for item in new_activity_a} == operation_ids
    assert {item.operation_id for item in new_activity_b} == operation_ids
    assert {item.direction for item in new_activity_a} == {
        ActivityDirection.SENT,
        ActivityDirection.RECEIVED,
    }
    assert {item.direction for item in new_activity_b} == {
        ActivityDirection.SENT,
        ActivityDirection.RECEIVED,
    }
    assert all(item.status == "POSTED" for item in new_activity_a)
    assert all(item.status == "POSTED" for item in new_activity_b)
