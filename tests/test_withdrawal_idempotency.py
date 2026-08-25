import time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from totally_testable_banking_api_tests.api_models import WithdrawalResponse
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


def _fund_account_and_wait_for_settlement(
    banking_api_client: BankingApiClient,
    *,
    account_id: UUID,
    access_token: str,
) -> None:
    funding = banking_api_client.create_deposit(
        destination_account_id=account_id,
        amount="100.00",
        access_token=access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    deadline = time.monotonic() + 10.0
    while True:
        current = banking_api_client.get_deposit(
            instruction_id=funding.id,
            access_token=access_token,
        )
        if current.status == "SETTLED":
            return
        if current.status == "FAILED":
            pytest.fail(f"Funding deposit failed with {current.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(f"Funding deposit did not settle; final status was {current.status!r}")
        time.sleep(0.1)


def _wait_for_withdrawal_settlement(
    banking_api_client: BankingApiClient,
    *,
    instruction_id: UUID,
    access_token: str,
) -> WithdrawalResponse:
    deadline = time.monotonic() + 10.0
    while True:
        current = banking_api_client.get_withdrawal(
            instruction_id=instruction_id,
            access_token=access_token,
        )
        if current.status == "SETTLED":
            return current
        if current.status == "FAILED":
            pytest.fail(f"Withdrawal failed with {current.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(f"Withdrawal did not settle; final status was {current.status!r}")
        time.sleep(0.1)


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

    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=account.id,
        access_token=token.access_token,
    )

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

    _wait_for_withdrawal_settlement(
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
        Decimal(account_before.settled_balance) - withdrawal_amount
    )
    assert Decimal(account_after.available_balance) == (
        Decimal(account_before.available_balance) - withdrawal_amount
    )
    assert len(activity_after) == len(activity_before) + 1
    assert sum(item.operation_id == first.id for item in activity_after) == 1


@pytest.mark.contract
@pytest.mark.negative
def test_changed_withdrawal_payload_with_reused_key_is_rejected_without_additional_effect(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]
    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=account.id,
        access_token=token.access_token,
    )

    idempotency_key = f"withdrawal-{uuid4()}"
    first = banking_api_client.create_withdrawal(
        source_account_id=account.id,
        amount="25.00",
        access_token=token.access_token,
        idempotency_key=idempotency_key,
    )
    _wait_for_withdrawal_settlement(
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
        banking_api_client.create_withdrawal(
            source_account_id=account.id,
            amount="30.00",
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


@pytest.mark.contract
@pytest.mark.invariant
def test_two_users_can_use_the_same_withdrawal_key_independently(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    first_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    first_account = banking_api_client.list_accounts(
        access_token=first_token.access_token,
    )[0]

    second_id = uuid4().hex
    second_email = f"api-test-user-{second_id}@example.com"
    second_password = f"Test-user-{second_id}"
    banking_api_client.register_user(
        email=second_email,
        display_name="Second Test User",
        password=second_password,
    )
    second_token = banking_api_client.login(
        email=second_email,
        password=second_password,
    )
    second_account = banking_api_client.list_accounts(
        access_token=second_token.access_token,
    )[0]

    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=first_account.id,
        access_token=first_token.access_token,
    )
    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=second_account.id,
        access_token=second_token.access_token,
    )

    first_before = banking_api_client.get_account(
        account_id=first_account.id,
        access_token=first_token.access_token,
    )
    second_before = banking_api_client.get_account(
        account_id=second_account.id,
        access_token=second_token.access_token,
    )
    first_activity_before = banking_api_client.list_activity(
        access_token=first_token.access_token,
    ).items
    second_activity_before = banking_api_client.list_activity(
        access_token=second_token.access_token,
    ).items

    shared_key = f"shared-withdrawal-{uuid4()}"
    first_withdrawal = banking_api_client.create_withdrawal(
        source_account_id=first_account.id,
        amount="25.00",
        access_token=first_token.access_token,
        idempotency_key=shared_key,
    )
    second_withdrawal = banking_api_client.create_withdrawal(
        source_account_id=second_account.id,
        amount="30.00",
        access_token=second_token.access_token,
        idempotency_key=shared_key,
    )

    _wait_for_withdrawal_settlement(
        banking_api_client,
        instruction_id=first_withdrawal.id,
        access_token=first_token.access_token,
    )
    _wait_for_withdrawal_settlement(
        banking_api_client,
        instruction_id=second_withdrawal.id,
        access_token=second_token.access_token,
    )

    first_after = banking_api_client.get_account(
        account_id=first_account.id,
        access_token=first_token.access_token,
    )
    second_after = banking_api_client.get_account(
        account_id=second_account.id,
        access_token=second_token.access_token,
    )
    first_activity_after = banking_api_client.list_activity(
        access_token=first_token.access_token,
    ).items
    second_activity_after = banking_api_client.list_activity(
        access_token=second_token.access_token,
    ).items

    assert first_withdrawal.id != second_withdrawal.id
    assert Decimal(first_after.settled_balance) == (
        Decimal(first_before.settled_balance) - Decimal("25.00")
    )
    assert Decimal(first_after.available_balance) == (
        Decimal(first_before.available_balance) - Decimal("25.00")
    )
    assert Decimal(second_after.settled_balance) == (
        Decimal(second_before.settled_balance) - Decimal("30.00")
    )
    assert Decimal(second_after.available_balance) == (
        Decimal(second_before.available_balance) - Decimal("30.00")
    )
    assert len(first_activity_after) == len(first_activity_before) + 1
    assert len(second_activity_after) == len(second_activity_before) + 1
    assert sum(item.operation_id == first_withdrawal.id for item in first_activity_after) == 1
    assert sum(item.operation_id == second_withdrawal.id for item in second_activity_after) == 1
    assert all(item.operation_id != second_withdrawal.id for item in first_activity_after)
    assert all(item.operation_id != first_withdrawal.id for item in second_activity_after)
