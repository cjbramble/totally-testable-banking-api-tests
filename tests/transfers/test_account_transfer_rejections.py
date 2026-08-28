"""Rejected own-account transfer behavior and financial invariants."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.setup_actions import UserAuthenticator, UserRegistrar
from totally_testable_banking_api_tests.test_data import FundedAccount


@pytest.mark.negative
@pytest.mark.invariant
def test_own_account_transfer_rejects_same_source_and_destination(
    banking_api_client: BankingApiClient,
    funded_account: FundedAccount,
) -> None:
    account_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_account_transfer(
            source_account_id=account_before.id,
            destination_account_id=account_before.id,
            amount="25.00",
            access_token=funded_account.access_token,
            idempotency_key=f"account-transfer-{uuid4()}",
        )

    account_after = banking_api_client.get_account(
        account_id=account_before.id,
        access_token=funded_account.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    error = exc_info.value

    assert error.status_code == 422
    assert error.error_code == "OWN_ACCOUNT_TRANSFER_REQUIRES_DISTINCT_ACCOUNTS"
    assert (
        account_after.settled_balance,
        account_after.available_balance,
    ) == (
        account_before.settled_balance,
        account_before.available_balance,
    )
    assert [item.operation_id for item in activity_after.items] == [
        item.operation_id for item in activity_before.items
    ]


@pytest.mark.negative
@pytest.mark.invariant
def test_own_account_transfer_rejects_foreign_destination(
    banking_api_client: BankingApiClient,
    funded_account: FundedAccount,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
) -> None:
    other_user = authenticate_user(register_user(display_name="Other Test User"))
    other_savings_before = other_user.savings
    owner_checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    owner_activity_before = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    other_activity_before = banking_api_client.list_activity(
        access_token=other_user.access_token,
        limit=100,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_account_transfer(
            source_account_id=owner_checking_before.id,
            destination_account_id=other_savings_before.id,
            amount="25.00",
            access_token=funded_account.access_token,
            idempotency_key=f"account-transfer-{uuid4()}",
        )

    owner_checking_after = banking_api_client.get_account(
        account_id=owner_checking_before.id,
        access_token=funded_account.access_token,
    )
    other_savings_after = banking_api_client.get_account(
        account_id=other_savings_before.id,
        access_token=other_user.access_token,
    )
    owner_activity_after = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    other_activity_after = banking_api_client.list_activity(
        access_token=other_user.access_token,
        limit=100,
    )
    error = exc_info.value

    assert error.status_code == 404
    assert error.error_code == "ACCOUNT_NOT_FOUND"
    assert (
        owner_checking_after.settled_balance,
        owner_checking_after.available_balance,
    ) == (
        owner_checking_before.settled_balance,
        owner_checking_before.available_balance,
    )
    assert (
        other_savings_after.settled_balance,
        other_savings_after.available_balance,
    ) == (
        other_savings_before.settled_balance,
        other_savings_before.available_balance,
    )
    assert [item.operation_id for item in owner_activity_after.items] == [
        item.operation_id for item in owner_activity_before.items
    ]
    assert [item.operation_id for item in other_activity_after.items] == [
        item.operation_id for item in other_activity_before.items
    ]


@pytest.mark.negative
@pytest.mark.invariant
def test_own_account_transfer_rejects_foreign_source(
    banking_api_client: BankingApiClient,
    funded_account: FundedAccount,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
) -> None:
    other_user = authenticate_user(register_user(display_name="Other Test User"))
    owner_checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    other_savings_before = banking_api_client.get_account(
        account_id=other_user.savings.id,
        access_token=other_user.access_token,
    )
    owner_activity_before = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    other_activity_before = banking_api_client.list_activity(
        access_token=other_user.access_token,
        limit=100,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_account_transfer(
            source_account_id=owner_checking_before.id,
            destination_account_id=other_savings_before.id,
            amount="25.00",
            access_token=other_user.access_token,
            idempotency_key=f"account-transfer-{uuid4()}",
        )

    owner_checking_after = banking_api_client.get_account(
        account_id=owner_checking_before.id,
        access_token=funded_account.access_token,
    )
    other_savings_after = banking_api_client.get_account(
        account_id=other_savings_before.id,
        access_token=other_user.access_token,
    )
    owner_activity_after = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    other_activity_after = banking_api_client.list_activity(
        access_token=other_user.access_token,
        limit=100,
    )
    error = exc_info.value

    assert error.status_code == 404
    assert error.error_code == "ACCOUNT_NOT_FOUND"
    assert (
        owner_checking_after.settled_balance,
        owner_checking_after.available_balance,
    ) == (
        owner_checking_before.settled_balance,
        owner_checking_before.available_balance,
    )
    assert (
        other_savings_after.settled_balance,
        other_savings_after.available_balance,
    ) == (
        other_savings_before.settled_balance,
        other_savings_before.available_balance,
    )
    assert [item.operation_id for item in owner_activity_after.items] == [
        item.operation_id for item in owner_activity_before.items
    ]
    assert [item.operation_id for item in other_activity_after.items] == [
        item.operation_id for item in other_activity_before.items
    ]
