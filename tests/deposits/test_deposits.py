"""Live deposit lifecycle, ownership, and terminal balance tests."""

import time
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    ActivityDirection,
    ActivityKind,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


def test_deposit_request_for_owned_account_is_accepted(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]

    deposit = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )

    assert deposit.id
    assert deposit.destination_account_id == account.id
    assert deposit.amount == "100.00"
    assert deposit.currency == "USD"
    assert deposit.status == "CREATED"
    assert deposit.failure_code is None
    assert deposit.completed_at is None


def test_created_deposit_can_be_retrieved_by_its_owner(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]
    deposit = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )

    retrieved = banking_api_client.get_deposit(
        instruction_id=deposit.id,
        access_token=token.access_token,
    )

    assert retrieved.id == deposit.id
    assert retrieved.destination_account_id == deposit.destination_account_id
    assert retrieved.status == "CREATED"


@pytest.mark.negative
def test_outsider_cannot_retrieve_another_users_deposit(
    banking_api_client: BankingApiClient,
    registered_user,
    registered_user_factory,
) -> None:
    owner_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    owner_account = banking_api_client.list_accounts(
        access_token=owner_token.access_token,
    )[0]
    deposit = banking_api_client.create_deposit(
        destination_account_id=owner_account.id,
        amount="100.00",
        access_token=owner_token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )

    outsider = registered_user_factory(display_name="Outsider Test User")
    outsider_token = banking_api_client.login(
        email=outsider.email,
        password=outsider.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.get_deposit(
            instruction_id=deposit.id,
            access_token=outsider_token.access_token,
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "DEPOSIT_NOT_FOUND"


@pytest.mark.invariant
def test_deposit_settlement_updates_balances_and_activity(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]
    assert account.settled_balance == "0.00"
    assert account.available_balance == "0.00"

    deposit = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    deadline = time.monotonic() + 10.0

    while True:
        current = banking_api_client.get_deposit(
            instruction_id=deposit.id,
            access_token=token.access_token,
        )
        if current.status == "SETTLED":
            break
        if current.status == "FAILED":
            pytest.fail(f"Deposit failed with {current.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(f"Deposit did not settle; final status was {current.status!r}")
        time.sleep(0.1)

    assert current.completed_at is not None
    settled_account = banking_api_client.list_accounts(
        access_token=token.access_token,
    )[0]
    matching_activity = [
        item
        for item in banking_api_client.list_activity(
            access_token=token.access_token,
        ).items
        if item.operation_id == deposit.id
    ]

    assert settled_account.id == account.id
    assert settled_account.settled_balance == "100.00"
    assert settled_account.available_balance == "100.00"
    assert len(matching_activity) == 1
    activity = matching_activity[0]
    assert activity.kind is ActivityKind.DEPOSIT
    assert activity.direction is ActivityDirection.CREDIT
    assert activity.account_id == account.id
    assert activity.amount == "100.00"
    assert activity.currency == "USD"
    assert activity.status == "SETTLED"
    assert activity.completed_at is not None
