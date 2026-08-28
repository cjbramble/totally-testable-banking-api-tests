"""Deposit idempotency tests proving one terminal credit and activity record."""

from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.operation_polling import wait_for_settlement
from totally_testable_banking_api_tests.setup_actions import UserAuthenticator, UserRegistrar
from totally_testable_banking_api_tests.test_data import RegisteredUser


@pytest.mark.invariant
def test_replayed_deposit_has_one_identity_and_one_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
) -> None:
    authenticated = authenticate_user(registered_user)
    account_before = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=authenticated.access_token,
    ).items

    deposit_amount = Decimal("100.00")
    idempotency_key = f"deposit-{uuid4()}"
    first = banking_api_client.create_deposit(
        destination_account_id=authenticated.checking.id,
        amount=str(deposit_amount),
        access_token=authenticated.access_token,
        idempotency_key=idempotency_key,
    )
    replay = banking_api_client.create_deposit(
        destination_account_id=authenticated.checking.id,
        amount=str(deposit_amount),
        access_token=authenticated.access_token,
        idempotency_key=idempotency_key,
    )

    wait_for_settlement(
        lambda: banking_api_client.get_deposit(
            instruction_id=first.id,
            access_token=authenticated.access_token,
        ),
        operation_name="deposit",
    )

    account_after = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=authenticated.access_token,
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


@pytest.mark.negative
def test_changed_deposit_payload_with_reused_key_is_rejected_without_additional_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
) -> None:
    authenticated = authenticate_user(registered_user)
    idempotency_key = f"deposit-{uuid4()}"
    first = banking_api_client.create_deposit(
        destination_account_id=authenticated.checking.id,
        amount="100.00",
        access_token=authenticated.access_token,
        idempotency_key=idempotency_key,
    )
    wait_for_settlement(
        lambda: banking_api_client.get_deposit(
            instruction_id=first.id,
            access_token=authenticated.access_token,
        ),
        operation_name="deposit",
    )

    account_after_first = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    activity_after_first = banking_api_client.list_activity(
        access_token=authenticated.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_deposit(
            destination_account_id=authenticated.checking.id,
            amount="125.00",
            access_token=authenticated.access_token,
            idempotency_key=idempotency_key,
        )

    error = exc_info.value
    assert error.status_code == 409
    assert error.error_code == "IDEMPOTENCY_PAYLOAD_MISMATCH"

    account_after_rejection = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    activity_after_rejection = banking_api_client.list_activity(
        access_token=authenticated.access_token,
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


@pytest.mark.invariant
def test_two_users_can_use_the_same_deposit_key_independently(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
) -> None:
    first = authenticate_user(registered_user)
    second = authenticate_user(
        register_user(display_name="Second Test User"),
    )

    first_before = banking_api_client.get_account(
        account_id=first.checking.id,
        access_token=first.access_token,
    )
    second_before = banking_api_client.get_account(
        account_id=second.checking.id,
        access_token=second.access_token,
    )
    first_activity_before = banking_api_client.list_activity(
        access_token=first.access_token,
    ).items
    second_activity_before = banking_api_client.list_activity(
        access_token=second.access_token,
    ).items

    shared_key = f"shared-deposit-{uuid4()}"
    first_deposit = banking_api_client.create_deposit(
        destination_account_id=first.checking.id,
        amount="100.00",
        access_token=first.access_token,
        idempotency_key=shared_key,
    )
    second_deposit = banking_api_client.create_deposit(
        destination_account_id=second.checking.id,
        amount="125.00",
        access_token=second.access_token,
        idempotency_key=shared_key,
    )

    wait_for_settlement(
        lambda: banking_api_client.get_deposit(
            instruction_id=first_deposit.id,
            access_token=first.access_token,
        ),
        operation_name="first user's deposit",
    )
    wait_for_settlement(
        lambda: banking_api_client.get_deposit(
            instruction_id=second_deposit.id,
            access_token=second.access_token,
        ),
        operation_name="second user's deposit",
    )

    first_after = banking_api_client.get_account(
        account_id=first.checking.id,
        access_token=first.access_token,
    )
    second_after = banking_api_client.get_account(
        account_id=second.checking.id,
        access_token=second.access_token,
    )
    first_activity_after = banking_api_client.list_activity(
        access_token=first.access_token,
    ).items
    second_activity_after = banking_api_client.list_activity(
        access_token=second.access_token,
    ).items

    assert first_deposit.id != second_deposit.id
    assert Decimal(first_after.settled_balance) == (
        Decimal(first_before.settled_balance) + Decimal("100.00")
    )
    assert Decimal(first_after.available_balance) == (
        Decimal(first_before.available_balance) + Decimal("100.00")
    )
    assert Decimal(second_after.settled_balance) == (
        Decimal(second_before.settled_balance) + Decimal("125.00")
    )
    assert Decimal(second_after.available_balance) == (
        Decimal(second_before.available_balance) + Decimal("125.00")
    )
    assert len(first_activity_after) == len(first_activity_before) + 1
    assert len(second_activity_after) == len(second_activity_before) + 1
    assert sum(item.operation_id == first_deposit.id for item in first_activity_after) == 1
    assert sum(item.operation_id == second_deposit.id for item in second_activity_after) == 1
    assert all(item.operation_id != second_deposit.id for item in first_activity_after)
    assert all(item.operation_id != first_deposit.id for item in second_activity_after)
