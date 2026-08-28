"""Live contract tests across the banking-service and simulated-processor boundary."""

import time
from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    ActivityDirection,
    ActivityKind,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.operation_polling import wait_for_terminal_status
from totally_testable_banking_api_tests.processor_control import (
    ProcessorCommandStatus,
    ProcessorControlClient,
    ProcessorOperation,
    ProcessorOutcome,
    ProcessorScenario,
)
from totally_testable_banking_api_tests.setup_actions import UserAuthenticator
from totally_testable_banking_api_tests.test_data import FundedAccount, RegisteredUser


@pytest.mark.contract
@pytest.mark.invariant
def test_declined_deposit_appears_as_failed_activity_without_balance_change(
    banking_api_client: BankingApiClient,
    processor_control_client: ProcessorControlClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
) -> None:
    authenticated = authenticate_user(registered_user)
    account_before = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    operation_key = f"deposit-decline-{uuid4()}"
    processor_control_client.configure_scenario(
        operation=ProcessorOperation.DEPOSIT,
        operation_key=operation_key,
        scenario=ProcessorScenario.DEPOSIT_DECLINE,
    )

    deposit = banking_api_client.create_deposit(
        destination_account_id=authenticated.checking.id,
        amount="25.00",
        access_token=authenticated.access_token,
        idempotency_key=operation_key,
    )
    current = wait_for_terminal_status(
        lambda: banking_api_client.get_deposit(
            instruction_id=deposit.id,
            access_token=authenticated.access_token,
        ),
        operation_name="processor-backed deposit",
        terminal_statuses={"FAILED", "SETTLED"},
    )

    account_after = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    matching_activity = [
        item
        for item in banking_api_client.list_activity(
            access_token=authenticated.access_token,
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
    assert activity.account_id == authenticated.checking.id
    assert activity.amount == "25.00"
    assert activity.currency == "USD"
    assert activity.status == "FAILED"
    assert activity.failure_code == "DECLINED"
    assert activity.completed_at is not None


@pytest.mark.contract
@pytest.mark.invariant
def test_declined_withdrawal_appears_as_failed_activity_without_balance_change(
    banking_api_client: BankingApiClient,
    processor_control_client: ProcessorControlClient,
    funded_account: FundedAccount,
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
    current = wait_for_terminal_status(
        lambda: banking_api_client.get_withdrawal(
            instruction_id=withdrawal.id,
            access_token=funded_account.access_token,
        ),
        operation_name="processor-backed withdrawal",
        terminal_statuses={"FAILED", "SETTLED"},
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
    assert activity.kind is ActivityKind.WITHDRAWAL
    assert activity.direction is ActivityDirection.DEBIT
    assert activity.account_id == account_before.id
    assert activity.amount == "25.00"
    assert activity.currency == "USD"
    assert activity.status == "FAILED"
    assert activity.failure_code == "DECLINED"
    assert activity.completed_at is not None


@pytest.mark.contract
@pytest.mark.invariant
def test_pending_withdrawal_reserves_available_balance_until_settlement(
    banking_api_client: BankingApiClient,
    processor_control_client: ProcessorControlClient,
    funded_account: FundedAccount,
) -> None:
    withdrawal_amount = Decimal("25.00")
    account_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    operation_key = f"withdrawal-pending-{uuid4()}"
    processor_control_client.configure_scenario(
        operation=ProcessorOperation.WITHDRAWAL,
        operation_key=operation_key,
        scenario=ProcessorScenario.WITHDRAWAL_PENDING,
    )

    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=account_before.id,
        amount=str(withdrawal_amount),
        access_token=funded_account.access_token,
        idempotency_key=operation_key,
    )
    account_while_pending = banking_api_client.get_account(
        account_id=account_before.id,
        access_token=funded_account.access_token,
    )

    assert withdrawal.status == "CREATED"
    assert Decimal(account_while_pending.settled_balance) == Decimal(account_before.settled_balance)
    assert Decimal(account_while_pending.available_balance) == (
        Decimal(account_before.available_balance) - withdrawal_amount
    )

    control_deadline = time.monotonic() + 10.0
    while True:
        try:
            processor_control_client.settle_pending_command(
                bank_instruction_id=withdrawal.id,
            )
            break
        except UnexpectedStatusError as error:
            if error.status_code != 404:
                raise
            if time.monotonic() >= control_deadline:
                pytest.fail("Processor did not accept the pending withdrawal before the deadline")
            time.sleep(0.1)

    current = wait_for_terminal_status(
        lambda: banking_api_client.get_withdrawal(
            instruction_id=withdrawal.id,
            access_token=funded_account.access_token,
        ),
        operation_name="pending processor-backed withdrawal",
        terminal_statuses={"FAILED", "SETTLED"},
    )

    account_after = banking_api_client.get_account(
        account_id=account_before.id,
        access_token=funded_account.access_token,
    )

    assert current.status == "SETTLED"
    assert current.failure_code is None
    assert current.completed_at is not None
    assert Decimal(account_after.settled_balance) == (
        Decimal(account_before.settled_balance) - withdrawal_amount
    )
    assert Decimal(account_after.available_balance) == (
        Decimal(account_before.available_balance) - withdrawal_amount
    )


@pytest.mark.contract
@pytest.mark.invariant
def test_duplicate_processor_callback_has_one_withdrawal_effect(
    banking_api_client: BankingApiClient,
    processor_control_client: ProcessorControlClient,
    funded_account: FundedAccount,
) -> None:
    withdrawal_amount = Decimal("25.00")
    account_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=funded_account.access_token,
    ).items
    operation_key = f"withdrawal-duplicate-{uuid4()}"
    processor_control_client.configure_scenario(
        operation=ProcessorOperation.WITHDRAWAL,
        operation_key=operation_key,
        scenario=ProcessorScenario.WITHDRAWAL_DUPLICATE_CALLBACK,
    )

    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=account_before.id,
        amount=str(withdrawal_amount),
        access_token=funded_account.access_token,
        idempotency_key=operation_key,
    )
    delivery_deadline = time.monotonic() + 10.0

    while True:
        try:
            observed = processor_control_client.observe_command(
                bank_instruction_id=withdrawal.id,
            )
        except UnexpectedStatusError as error:
            if error.status_code != 404:
                raise
        else:
            if observed.callback_successful_delivery_count == 2:
                break
            if observed.callback_successful_delivery_count > 2:
                pytest.fail(
                    "Processor delivered more callbacks than the configured scenario required"
                )
        if time.monotonic() >= delivery_deadline:
            pytest.fail("Processor did not complete two callback deliveries before the deadline")
        time.sleep(0.1)

    current = banking_api_client.get_withdrawal(
        instruction_id=withdrawal.id,
        access_token=funded_account.access_token,
    )
    account_after = banking_api_client.get_account(
        account_id=account_before.id,
        access_token=funded_account.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=funded_account.access_token,
    ).items
    matching_activity = [item for item in activity_after if item.operation_id == withdrawal.id]

    assert observed.operation is ProcessorOperation.WITHDRAWAL
    assert observed.operation_key == operation_key
    assert observed.bank_instruction_id == withdrawal.id
    assert observed.status is ProcessorCommandStatus.TERMINAL
    assert observed.outcome is ProcessorOutcome.SETTLED
    assert observed.failure_code is None
    assert observed.callback_required_delivery_count == 2
    assert observed.callback_successful_delivery_count == 2
    assert current.status == "SETTLED"
    assert current.failure_code is None
    assert current.completed_at is not None
    assert Decimal(account_after.settled_balance) == (
        Decimal(account_before.settled_balance) - withdrawal_amount
    )
    assert Decimal(account_after.available_balance) == (
        Decimal(account_before.available_balance) - withdrawal_amount
    )
    assert len(activity_after) == len(activity_before) + 1
    assert len(matching_activity) == 1
    activity = matching_activity[0]
    assert activity.kind is ActivityKind.WITHDRAWAL
    assert activity.direction is ActivityDirection.DEBIT
    assert activity.account_id == account_before.id
    assert activity.amount == str(withdrawal_amount)
    assert activity.currency == "USD"
    assert activity.status == "SETTLED"
    assert activity.failure_code is None
