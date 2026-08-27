"""Live withdrawal acceptance and lifecycle tests."""

from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    ActivityDirection,
    ActivityKind,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.operation_polling import wait_for_settlement


def test_withdrawal_request_for_owned_account_is_accepted(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=funded_account.account.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
    )

    assert withdrawal.id
    assert withdrawal.source_account_id == funded_account.account.id
    assert withdrawal.amount == "25.00"
    assert withdrawal.currency == "USD"
    assert withdrawal.status == "CREATED"
    assert withdrawal.failure_code is None
    assert withdrawal.completed_at is None


def test_created_withdrawal_can_be_retrieved_by_its_owner(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=funded_account.account.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
    )

    retrieved = banking_api_client.get_withdrawal(
        instruction_id=withdrawal.id,
        access_token=funded_account.access_token,
    )

    assert retrieved.id == withdrawal.id
    assert retrieved.source_account_id == withdrawal.source_account_id
    assert retrieved.amount == withdrawal.amount
    assert retrieved.currency == withdrawal.currency
    assert retrieved.created_at == withdrawal.created_at


@pytest.mark.negative
def test_outsider_cannot_retrieve_another_users_withdrawal(
    banking_api_client: BankingApiClient,
    funded_account,
    registered_user_factory,
) -> None:
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=funded_account.account.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
    )

    outsider = registered_user_factory(display_name="Outsider Test User")
    outsider_token = banking_api_client.login(
        email=outsider.email,
        password=outsider.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.get_withdrawal(
            instruction_id=withdrawal.id,
            access_token=outsider_token.access_token,
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "WITHDRAWAL_NOT_FOUND"


@pytest.mark.invariant
def test_withdrawal_settlement_updates_balances_and_activity(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    withdrawal_amount = Decimal("25.00")
    account_before = funded_account.account
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=account_before.id,
        amount=str(withdrawal_amount),
        access_token=funded_account.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
    )
    current = wait_for_settlement(
        lambda: banking_api_client.get_withdrawal(
            instruction_id=withdrawal.id,
            access_token=funded_account.access_token,
        ),
        operation_name="withdrawal",
    )

    account_after = banking_api_client.get_account(
        account_id=account_before.id,
        access_token=funded_account.access_token,
    )
    matching_activity = [
        item
        for item in banking_api_client.list_activity(
            access_token=funded_account.access_token,
        ).items
        if item.operation_id == withdrawal.id
    ]

    assert current.completed_at is not None
    assert Decimal(account_after.settled_balance) == (
        Decimal(account_before.settled_balance) - withdrawal_amount
    )
    assert Decimal(account_after.available_balance) == (
        Decimal(account_before.available_balance) - withdrawal_amount
    )
    assert len(matching_activity) == 1
    activity = matching_activity[0]
    assert activity.kind is ActivityKind.WITHDRAWAL
    assert activity.direction is ActivityDirection.DEBIT
    assert activity.account_id == account_before.id
    assert activity.amount == str(withdrawal_amount)
    assert activity.currency == "USD"
    assert activity.status == "SETTLED"
    assert activity.completed_at is not None
