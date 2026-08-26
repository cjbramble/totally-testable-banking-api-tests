"""Live contract tests across the banking-service and simulated-processor boundary."""

import time
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    ActivityDirection,
    ActivityKind,
    ProductAccountType,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.processor_control import (
    ProcessorControlClient,
    ProcessorOperation,
    ProcessorScenario,
)


@pytest.mark.contract
@pytest.mark.invariant
def test_declined_deposit_appears_as_failed_activity_without_balance_change(
    banking_api_client: BankingApiClient,
    processor_control_client: ProcessorControlClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=token.access_token,
        )
        if account.account_type is ProductAccountType.CHECKING
    )
    account_before = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    operation_key = f"deposit-decline-{uuid4()}"
    processor_control_client.configure_scenario(
        operation=ProcessorOperation.DEPOSIT,
        operation_key=operation_key,
        scenario=ProcessorScenario.DEPOSIT_DECLINE,
    )

    deposit = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="25.00",
        access_token=token.access_token,
        idempotency_key=operation_key,
    )
    deadline = time.monotonic() + 10.0

    while True:
        current = banking_api_client.get_deposit(
            instruction_id=deposit.id,
            access_token=token.access_token,
        )
        if current.status in {"FAILED", "SETTLED"}:
            break
        if time.monotonic() >= deadline:
            pytest.fail(f"Deposit did not finish; final status was {current.status!r}")
        time.sleep(0.1)

    account_after = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    matching_activity = [
        item
        for item in banking_api_client.list_activity(
            access_token=token.access_token,
        ).items
        if item.operation_id == deposit.id
    ]

    assert current.status == "FAILED"
    assert current.failure_code == "DECLINED"
    assert current.completed_at is not None
    assert (
        account_after.settled_balance,
        account_after.available_balance,
    ) == (
        account_before.settled_balance,
        account_before.available_balance,
    )
    assert len(matching_activity) == 1
    activity = matching_activity[0]
    assert activity.kind is ActivityKind.DEPOSIT
    assert activity.direction is ActivityDirection.CREDIT
    assert activity.account_id == account.id
    assert activity.amount == "25.00"
    assert activity.currency == "USD"
    assert activity.status == "FAILED"
    assert activity.failure_code == "DECLINED"
    assert activity.completed_at is not None


@pytest.mark.contract
@pytest.mark.invariant
def test_declined_withdrawal_fails_without_changing_account_balance(
    banking_api_client: BankingApiClient,
    processor_control_client: ProcessorControlClient,
    funded_account,
) -> None:
    account_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    operation_key = f"withdrawal-decline-{uuid4()}"
    processor_control_client.configure_scenario(
        operation=ProcessorOperation.WITHDRAWAL,
        operation_key=operation_key,
        scenario=ProcessorScenario.WITHDRAWAL_DECLINE,
    )

    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=account_before.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=operation_key,
    )
    deadline = time.monotonic() + 10.0

    while True:
        current = banking_api_client.get_withdrawal(
            instruction_id=withdrawal.id,
            access_token=funded_account.access_token,
        )
        if current.status in {"FAILED", "SETTLED"}:
            break
        if time.monotonic() >= deadline:
            pytest.fail(f"Withdrawal did not finish; final status was {current.status!r}")
        time.sleep(0.1)

    account_after = banking_api_client.get_account(
        account_id=account_before.id,
        access_token=funded_account.access_token,
    )

    assert current.status == "FAILED"
    assert current.failure_code == "DECLINED"
    assert current.completed_at is not None
    assert (
        account_after.settled_balance,
        account_after.available_balance,
    ) == (
        account_before.settled_balance,
        account_before.available_balance,
    )
