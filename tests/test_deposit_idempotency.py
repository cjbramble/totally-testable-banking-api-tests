import time
from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.contract
@pytest.mark.invariant
def test_replayed_deposit_has_one_identity_and_one_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]
    account_before = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=token.access_token,
    ).items

    deposit_amount = Decimal("100.00")
    idempotency_key = f"deposit-{uuid4()}"
    first = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount=str(deposit_amount),
        access_token=token.access_token,
        idempotency_key=idempotency_key,
    )
    replay = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount=str(deposit_amount),
        access_token=token.access_token,
        idempotency_key=idempotency_key,
    )

    deadline = time.monotonic() + 10.0
    while True:
        current = banking_api_client.get_deposit(
            instruction_id=first.id,
            access_token=token.access_token,
        )
        if current.status == "SETTLED":
            break
        if current.status == "FAILED":
            pytest.fail(f"Deposit failed with {current.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(f"Deposit did not settle; final status was {current.status!r}")
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
        Decimal(account_before.settled_balance) + deposit_amount
    )
    assert Decimal(account_after.available_balance) == (
        Decimal(account_before.available_balance) + deposit_amount
    )
    assert len(activity_after) == len(activity_before) + 1
    assert sum(item.operation_id == first.id for item in activity_after) == 1
