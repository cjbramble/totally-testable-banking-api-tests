"""Live contract tests across the banking-service and simulated-processor boundary."""

import time
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.processor_control import (
    ProcessorControlClient,
    ProcessorOperation,
    ProcessorScenario,
)


@pytest.mark.contract
@pytest.mark.invariant
def test_declined_deposit_fails_without_changing_account_balance(
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
