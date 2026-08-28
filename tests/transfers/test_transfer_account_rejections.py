"""P2P transfer account relationship and balance rejections."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserAuthenticator,
    UserRegistrar,
)
from totally_testable_banking_api_tests.test_data import RegisteredUser


@pytest.mark.negative
def test_foreign_source_account_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    owner = authenticate_user(registered_user)

    create_settled_deposit(
        destination_account_id=owner.checking.id,
        access_token=owner.access_token,
    )

    actor = authenticate_user(
        register_user(display_name="Actor Test User"),
    )

    source_before = banking_api_client.get_account(
        account_id=owner.checking.id,
        access_token=owner.access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=actor.checking.id,
        access_token=actor.access_token,
    )
    owner_activity_before = banking_api_client.list_activity(
        access_token=owner.access_token,
    ).items
    actor_activity_before = banking_api_client.list_activity(
        access_token=actor.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=owner.checking.id,
            destination_account_id=actor.checking.id,
            amount="25.00",
            access_token=actor.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error_code == "ACCOUNT_NOT_FOUND"

    source_after = banking_api_client.get_account(
        account_id=owner.checking.id,
        access_token=owner.access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=actor.checking.id,
        access_token=actor.access_token,
    )
    owner_activity_after = banking_api_client.list_activity(
        access_token=owner.access_token,
    ).items
    actor_activity_after = banking_api_client.list_activity(
        access_token=actor.access_token,
    ).items

    assert (
        source_after.settled_balance,
        source_after.available_balance,
    ) == (
        source_before.settled_balance,
        source_before.available_balance,
    )
    assert (
        destination_after.settled_balance,
        destination_after.available_balance,
    ) == (
        destination_before.settled_balance,
        destination_before.available_balance,
    )
    assert owner_activity_after == owner_activity_before
    assert actor_activity_after == actor_activity_before


@pytest.mark.negative
def test_unknown_destination_account_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    sender = authenticate_user(registered_user)
    create_settled_deposit(
        destination_account_id=sender.checking.id,
        access_token=sender.access_token,
    )

    source_before = banking_api_client.get_account(
        account_id=sender.checking.id,
        access_token=sender.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender.checking.id,
            destination_account_id=uuid4(),
            amount="25.00",
            access_token=sender.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error_code == "RECIPIENT_ACCOUNT_NOT_FOUND"

    source_after = banking_api_client.get_account(
        account_id=sender.checking.id,
        access_token=sender.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items

    assert (
        source_after.settled_balance,
        source_after.available_balance,
    ) == (
        source_before.settled_balance,
        source_before.available_balance,
    )
    assert activity_after == activity_before


@pytest.mark.negative
def test_self_transfer_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    authenticated = authenticate_user(registered_user)
    create_settled_deposit(
        destination_account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )

    account_before = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=authenticated.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=authenticated.checking.id,
            destination_account_id=authenticated.checking.id,
            amount="25.00",
            access_token=authenticated.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error_code == "P2P_REQUIRES_DIFFERENT_USERS"

    account_after = banking_api_client.get_account(
        account_id=authenticated.checking.id,
        access_token=authenticated.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=authenticated.access_token,
    ).items

    assert (
        account_after.settled_balance,
        account_after.available_balance,
    ) == (
        account_before.settled_balance,
        account_before.available_balance,
    )
    assert activity_after == activity_before


@pytest.mark.negative
def test_transfer_exceeding_available_balance_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    sender = authenticate_user(registered_user)
    create_settled_deposit(
        destination_account_id=sender.checking.id,
        access_token=sender.access_token,
        amount="10.00",
    )

    recipient = authenticate_user(
        register_user(display_name="Recipient Test User"),
    )

    source_before = banking_api_client.get_account(
        account_id=sender.checking.id,
        access_token=sender.access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=recipient.checking.id,
        access_token=recipient.access_token,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=recipient.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender.checking.id,
            destination_account_id=recipient.checking.id,
            amount="25.00",
            access_token=sender.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 409
    assert error.error_code == "INSUFFICIENT_FUNDS"

    source_after = banking_api_client.get_account(
        account_id=sender.checking.id,
        access_token=sender.access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=recipient.checking.id,
        access_token=recipient.access_token,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=sender.access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=recipient.access_token,
    ).items

    assert (
        source_after.settled_balance,
        source_after.available_balance,
    ) == (
        source_before.settled_balance,
        source_before.available_balance,
    )
    assert (
        destination_after.settled_balance,
        destination_after.available_balance,
    ) == (
        destination_before.settled_balance,
        destination_before.available_balance,
    )
    assert sender_activity_after == sender_activity_before
    assert recipient_activity_after == recipient_activity_before
