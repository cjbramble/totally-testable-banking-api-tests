"""Activity keyset pagination traversal and isolation behavior."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import ActivityKind
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.setup_actions import (
    UserRegistrar,
)
from totally_testable_banking_api_tests.test_data import (
    ActivityUserFunder,
    RegisteredUser,
)


@pytest.mark.invariant
def test_activity_page_boundaries_return_expected_operations_without_cursor(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    fund_activity_user: ActivityUserFunder,
) -> None:
    activity_user = fund_activity_user(registered_user)
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
    registered_user: RegisteredUser,
    fund_activity_user: ActivityUserFunder,
) -> None:
    activity_user = fund_activity_user(registered_user)
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
    registered_user: RegisteredUser,
    fund_activity_user: ActivityUserFunder,
) -> None:
    activity_user = fund_activity_user(registered_user)
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


@pytest.mark.invariant
def test_activity_cursor_from_another_user_does_not_expose_owner_activity(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    fund_activity_user: ActivityUserFunder,
) -> None:
    other = register_user(display_name="Other Test User")
    other_user = fund_activity_user(other)
    cursor_owner = fund_activity_user(registered_user)
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
