"""Activity projection and keyset pagination tests."""

import time
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ActivityDirection,
    ActivityKind,
    ProductAccountType,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@dataclass(frozen=True)
class _FundedActivityUser:
    access_token: str
    checking: AccountResponse
    savings: AccountResponse
    deposit_id: UUID


def _wait_for_deposit_settlement(
    banking_api_client: BankingApiClient,
    *,
    instruction_id: UUID,
    access_token: str,
) -> None:
    deadline = time.monotonic() + 10.0
    while True:
        current = banking_api_client.get_deposit(
            instruction_id=instruction_id,
            access_token=access_token,
        )
        if current.status == "SETTLED":
            return
        if current.status == "FAILED":
            pytest.fail(f"Funding deposit failed with {current.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(f"Funding deposit did not settle; final status was {current.status!r}")
        time.sleep(0.1)


def _create_funded_activity_user(
    banking_api_client: BankingApiClient,
    *,
    email: str,
    password: str,
) -> _FundedActivityUser:
    token = banking_api_client.login(email=email, password=password)
    accounts = banking_api_client.list_accounts(access_token=token.access_token)
    checking = next(
        account for account in accounts if account.account_type is ProductAccountType.CHECKING
    )
    savings = next(
        account for account in accounts if account.account_type is ProductAccountType.SAVINGS
    )
    deposit = banking_api_client.create_deposit(
        destination_account_id=checking.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    _wait_for_deposit_settlement(
        banking_api_client,
        instruction_id=deposit.id,
        access_token=token.access_token,
    )
    return _FundedActivityUser(
        access_token=token.access_token,
        checking=checking,
        savings=savings,
        deposit_id=deposit.id,
    )


@pytest.mark.invariant
def test_transfer_appears_as_sent_and_received_activity(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    sender_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    sender_account = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]

    recipient_id = uuid4().hex
    recipient_email = f"api-test-user-{recipient_id}@example.com"
    recipient_password = f"Test-user-{recipient_id}"
    banking_api_client.register_user(
        email=recipient_email,
        display_name="Recipient Test User",
        password=recipient_password,
    )
    recipient_token = banking_api_client.login(
        email=recipient_email,
        password=recipient_password,
    )
    recipient_account = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]

    funding = banking_api_client.create_deposit(
        destination_account_id=sender_account.id,
        amount="100.00",
        access_token=sender_token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    _wait_for_deposit_settlement(
        banking_api_client,
        instruction_id=funding.id,
        access_token=sender_token.access_token,
    )

    transfer = banking_api_client.create_transfer(
        source_account_id=sender_account.id,
        destination_account_id=recipient_account.id,
        amount="25.00",
        access_token=sender_token.access_token,
        idempotency_key=f"transfer-{uuid4()}",
    )

    sender_page = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    )
    recipient_page = banking_api_client.list_activity(
        access_token=recipient_token.access_token,
    )
    sender_matches = [item for item in sender_page.items if item.operation_id == transfer.id]
    recipient_matches = [item for item in recipient_page.items if item.operation_id == transfer.id]

    assert len(sender_matches) == 1
    assert len(recipient_matches) == 1
    sender_activity = sender_matches[0]
    recipient_activity = recipient_matches[0]

    assert sender_activity.kind == ActivityKind.TRANSFER
    assert sender_activity.direction == ActivityDirection.SENT
    assert sender_activity.account_id == sender_account.id
    assert sender_activity.amount == "25.00"
    assert sender_activity.currency == "USD"
    assert sender_activity.status == "POSTED"

    assert recipient_activity.kind == ActivityKind.TRANSFER
    assert recipient_activity.direction == ActivityDirection.RECEIVED
    assert recipient_activity.account_id == recipient_account.id
    assert recipient_activity.amount == "25.00"
    assert recipient_activity.currency == "USD"
    assert recipient_activity.status == "POSTED"


@pytest.mark.invariant
def test_activity_page_boundaries_return_expected_operations_without_cursor(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    activity_user = _create_funded_activity_user(
        banking_api_client,
        email=registered_user.email,
        password=registered_user.password,
    )
    account_transfer = banking_api_client.create_account_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=activity_user.savings.id,
        amount="25.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )

    expected_operation_ids = [account_transfer.id, activity_user.deposit_id]

    exact_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
    )

    assert [item.operation_id for item in exact_page.items] == expected_operation_ids
    assert [item.kind for item in exact_page.items] == [
        ActivityKind.ACCOUNT_TRANSFER,
        ActivityKind.DEPOSIT,
    ]
    assert exact_page.next_cursor is None

    partial_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=3,
    )

    assert [item.operation_id for item in partial_page.items] == expected_operation_ids
    assert partial_page.next_cursor is None


@pytest.mark.invariant
def test_activity_cursor_traversal_has_no_duplicate_or_missing_operations(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    activity_user = _create_funded_activity_user(
        banking_api_client,
        email=registered_user.email,
        password=registered_user.password,
    )
    first_transfer = banking_api_client.create_account_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=activity_user.savings.id,
        amount="25.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    second_transfer = banking_api_client.create_account_transfer(
        source_account_id=activity_user.savings.id,
        destination_account_id=activity_user.checking.id,
        amount="10.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    expected_operation_ids = [
        second_transfer.id,
        first_transfer.id,
        activity_user.deposit_id,
    ]

    first_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
    )
    cursor = first_page.next_cursor
    assert cursor is not None

    second_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
        cursor=cursor,
    )
    collected_operation_ids = [item.operation_id for item in first_page.items] + [
        item.operation_id for item in second_page.items
    ]

    assert collected_operation_ids == expected_operation_ids
    assert len(collected_operation_ids) == len(set(collected_operation_ids))
    assert second_page.next_cursor is None


@pytest.mark.invariant
def test_activity_cursor_remains_stable_when_newer_operation_is_inserted(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    activity_user = _create_funded_activity_user(
        banking_api_client,
        email=registered_user.email,
        password=registered_user.password,
    )
    first_transfer = banking_api_client.create_account_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=activity_user.savings.id,
        amount="25.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    second_transfer = banking_api_client.create_account_transfer(
        source_account_id=activity_user.savings.id,
        destination_account_id=activity_user.checking.id,
        amount="10.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    expected_snapshot_ids = [
        second_transfer.id,
        first_transfer.id,
        activity_user.deposit_id,
    ]

    first_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
    )
    cursor = first_page.next_cursor
    assert cursor is not None

    inserted_transfer = banking_api_client.create_account_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=activity_user.savings.id,
        amount="5.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )

    second_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
        cursor=cursor,
    )
    collected_snapshot_ids = [item.operation_id for item in first_page.items] + [
        item.operation_id for item in second_page.items
    ]
    fresh_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=2,
    )

    assert collected_snapshot_ids == expected_snapshot_ids
    assert len(collected_snapshot_ids) == len(set(collected_snapshot_ids))
    assert inserted_transfer.id not in collected_snapshot_ids
    assert [item.operation_id for item in fresh_page.items] == [
        inserted_transfer.id,
        second_transfer.id,
    ]


@pytest.mark.negative
def test_malformed_activity_cursor_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.list_activity(
            access_token=token.access_token,
            cursor="not-a-valid-cursor",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == "INVALID_CURSOR"


@pytest.mark.negative
def test_altered_activity_cursor_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    activity_user = _create_funded_activity_user(
        banking_api_client,
        email=registered_user.email,
        password=registered_user.password,
    )
    banking_api_client.create_account_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=activity_user.savings.id,
        amount="25.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    first_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=1,
    )
    cursor = first_page.next_cursor
    assert cursor is not None

    mutation_index = len(cursor) // 2
    replacement = "A" if cursor[mutation_index] != "A" else "B"
    altered_cursor = cursor[:mutation_index] + replacement + cursor[mutation_index + 1 :]

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.list_activity(
            access_token=activity_user.access_token,
            cursor=altered_cursor,
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == "INVALID_CURSOR"


@pytest.mark.invariant
def test_activity_cursor_from_another_user_does_not_expose_owner_activity(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    other_id = uuid4().hex
    other_email = f"api-test-user-{other_id}@example.com"
    other_password = f"Test-user-{other_id}"
    banking_api_client.register_user(
        email=other_email,
        display_name="Other Test User",
        password=other_password,
    )
    other_user = _create_funded_activity_user(
        banking_api_client,
        email=other_email,
        password=other_password,
    )
    cursor_owner = _create_funded_activity_user(
        banking_api_client,
        email=registered_user.email,
        password=registered_user.password,
    )
    owner_transfer = banking_api_client.create_account_transfer(
        source_account_id=cursor_owner.checking.id,
        destination_account_id=cursor_owner.savings.id,
        amount="25.00",
        access_token=cursor_owner.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    owner_page = banking_api_client.list_activity(
        access_token=cursor_owner.access_token,
        limit=1,
    )
    owner_cursor = owner_page.next_cursor
    assert owner_cursor is not None

    other_page = banking_api_client.list_activity(
        access_token=other_user.access_token,
        limit=10,
        cursor=owner_cursor,
    )
    returned_operation_ids = [item.operation_id for item in other_page.items]

    assert returned_operation_ids == [other_user.deposit_id]
    assert {owner_transfer.id, cursor_owner.deposit_id}.isdisjoint(returned_operation_ids)


@pytest.mark.parametrize(
    "limit",
    [1, 100],
    ids=["minimum", "maximum"],
)
def test_activity_limit_accepts_documented_boundaries(
    banking_api_client: BankingApiClient,
    registered_user,
    limit: int,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )

    page = banking_api_client.list_activity(
        access_token=token.access_token,
        limit=limit,
    )

    assert page.items == []
    assert page.next_cursor is None
