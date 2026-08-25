import time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from totally_testable_banking_api_tests.api_models import DepositResponse
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


def _wait_for_deposit_settlement(
    banking_api_client: BankingApiClient,
    *,
    instruction_id: UUID,
    access_token: str,
) -> DepositResponse:
    deadline = time.monotonic() + 10.0
    while True:
        current = banking_api_client.get_deposit(
            instruction_id=instruction_id,
            access_token=access_token,
        )
        if current.status == "SETTLED":
            return current
        if current.status == "FAILED":
            pytest.fail(f"Deposit failed with {current.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(f"Deposit did not settle; final status was {current.status!r}")
        time.sleep(0.1)


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

    _wait_for_deposit_settlement(
        banking_api_client,
        instruction_id=first.id,
        access_token=token.access_token,
    )

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


@pytest.mark.contract
@pytest.mark.negative
def test_changed_deposit_payload_with_reused_key_is_rejected_without_additional_effect(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]
    idempotency_key = f"deposit-{uuid4()}"
    first = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=idempotency_key,
    )
    _wait_for_deposit_settlement(
        banking_api_client,
        instruction_id=first.id,
        access_token=token.access_token,
    )

    account_after_first = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    activity_after_first = banking_api_client.list_activity(
        access_token=token.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_deposit(
            destination_account_id=account.id,
            amount="125.00",
            access_token=token.access_token,
            idempotency_key=idempotency_key,
        )

    error = exc_info.value
    assert error.status_code == 409
    assert error.error is not None
    assert error.error.error.code == "IDEMPOTENCY_PAYLOAD_MISMATCH"

    account_after_rejection = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    activity_after_rejection = banking_api_client.list_activity(
        access_token=token.access_token,
    ).items

    assert (
        account_after_rejection.settled_balance,
        account_after_rejection.available_balance,
    ) == (
        account_after_first.settled_balance,
        account_after_first.available_balance,
    )
    assert activity_after_rejection == activity_after_first
    assert sum(item.operation_id == first.id for item in activity_after_rejection) == 1
