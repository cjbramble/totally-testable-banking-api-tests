import time
from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.contract
@pytest.mark.invariant
def test_replayed_withdrawal_has_one_identity_and_one_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]

    funding = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    funding_deadline = time.monotonic() + 10.0
    while True:
        current_funding = banking_api_client.get_deposit(
            instruction_id=funding.id,
            access_token=token.access_token,
        )
        if current_funding.status == "SETTLED":
            break
        if current_funding.status == "FAILED":
            pytest.fail(f"Funding deposit failed with {current_funding.failure_code!r}")
        if time.monotonic() >= funding_deadline:
            pytest.fail(
                f"Funding deposit did not settle; final status was {current_funding.status!r}"
            )
        time.sleep(0.1)

    account_before = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=token.access_token,
    ).items

    withdrawal_amount = Decimal("25.00")
    idempotency_key = f"withdrawal-{uuid4()}"
    first = banking_api_client.create_withdrawal(
        source_account_id=account.id,
        amount=str(withdrawal_amount),
        access_token=token.access_token,
        idempotency_key=idempotency_key,
    )
    replay = banking_api_client.create_withdrawal(
        source_account_id=account.id,
        amount=str(withdrawal_amount),
        access_token=token.access_token,
        idempotency_key=idempotency_key,
    )

    withdrawal_deadline = time.monotonic() + 10.0
    while True:
        current_withdrawal = banking_api_client.get_withdrawal(
            instruction_id=first.id,
            access_token=token.access_token,
        )
        if current_withdrawal.status == "SETTLED":
            break
        if current_withdrawal.status == "FAILED":
            pytest.fail(f"Withdrawal failed with {current_withdrawal.failure_code!r}")
        if time.monotonic() >= withdrawal_deadline:
            pytest.fail(
                f"Withdrawal did not settle; final status was {current_withdrawal.status!r}"
            )
        time.sleep(0.1)

    account_after = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=token.access_token,
    ).items

    assert replay.id == first.id
    assert Decimal(account_after.settled_balance) == (
        Decimal(account_before.settled_balance) - withdrawal_amount
    )
    assert Decimal(account_after.available_balance) == (
        Decimal(account_before.available_balance) - withdrawal_amount
    )
    assert len(activity_after) == len(activity_before) + 1
    assert sum(item.operation_id == first.id for item in activity_after) == 1
