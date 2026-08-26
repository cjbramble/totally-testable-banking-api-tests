"""Live own-account transfer lifecycle and financial-invariant tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@pytest.mark.invariant
def test_immediate_checking_to_savings_transfer_moves_exact_amount(
    banking_api_client: BankingApiClient,
    registered_user,
    funded_account,
) -> None:
    savings_before = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=funded_account.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    transfer_amount = Decimal("25.00")

    transfer = banking_api_client.create_account_transfer(
        source_account_id=checking_before.id,
        destination_account_id=savings_before.id,
        amount=str(transfer_amount),
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )

    checking_after = banking_api_client.get_account(
        account_id=checking_before.id,
        access_token=funded_account.access_token,
    )
    savings_after = banking_api_client.get_account(
        account_id=savings_before.id,
        access_token=funded_account.access_token,
    )

    assert transfer.sender_user_id == registered_user.user.id
    assert transfer.recipient_user_id == registered_user.user.id
    assert transfer.source_account_id == checking_before.id
    assert transfer.destination_account_id == savings_before.id
    assert transfer.amount == "25.00"
    assert transfer.currency == "USD"
    assert transfer.status == "POSTED"
    assert transfer.transfer_kind == "OWN_ACCOUNT"
    assert transfer.scheduled_for is None
    assert transfer.completed_at is not None
    assert Decimal(checking_after.settled_balance) == (
        Decimal(checking_before.settled_balance) - transfer_amount
    )
    assert Decimal(checking_after.available_balance) == (
        Decimal(checking_before.available_balance) - transfer_amount
    )
    assert Decimal(savings_after.settled_balance) == (
        Decimal(savings_before.settled_balance) + transfer_amount
    )
    assert Decimal(savings_after.available_balance) == (
        Decimal(savings_before.available_balance) + transfer_amount
    )


@pytest.mark.invariant
def test_immediate_savings_to_checking_transfer_moves_exact_amount(
    banking_api_client: BankingApiClient,
    registered_user,
    funded_account,
) -> None:
    savings = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=funded_account.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    savings_funding = banking_api_client.create_account_transfer(
        source_account_id=funded_account.account.id,
        destination_account_id=savings.id,
        amount="30.00",
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    assert savings_funding.status == "POSTED"

    checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    savings_before = banking_api_client.get_account(
        account_id=savings.id,
        access_token=funded_account.access_token,
    )
    transfer_amount = Decimal("20.00")

    transfer = banking_api_client.create_account_transfer(
        source_account_id=savings_before.id,
        destination_account_id=checking_before.id,
        amount=str(transfer_amount),
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )

    checking_after = banking_api_client.get_account(
        account_id=checking_before.id,
        access_token=funded_account.access_token,
    )
    savings_after = banking_api_client.get_account(
        account_id=savings_before.id,
        access_token=funded_account.access_token,
    )

    assert transfer.sender_user_id == registered_user.user.id
    assert transfer.recipient_user_id == registered_user.user.id
    assert transfer.source_account_id == savings_before.id
    assert transfer.destination_account_id == checking_before.id
    assert transfer.amount == "20.00"
    assert transfer.currency == "USD"
    assert transfer.status == "POSTED"
    assert transfer.transfer_kind == "OWN_ACCOUNT"
    assert transfer.scheduled_for is None
    assert transfer.completed_at is not None
    assert Decimal(savings_after.settled_balance) == (
        Decimal(savings_before.settled_balance) - transfer_amount
    )
    assert Decimal(savings_after.available_balance) == (
        Decimal(savings_before.available_balance) - transfer_amount
    )
    assert Decimal(checking_after.settled_balance) == (
        Decimal(checking_before.settled_balance) + transfer_amount
    )
    assert Decimal(checking_after.available_balance) == (
        Decimal(checking_before.available_balance) + transfer_amount
    )


@pytest.mark.invariant
def test_future_account_transfer_has_no_early_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
    funded_account,
) -> None:
    savings_before = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=funded_account.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    scheduled_for = datetime.now(UTC).date() + timedelta(days=2)

    transfer = banking_api_client.create_account_transfer(
        source_account_id=checking_before.id,
        destination_account_id=savings_before.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
        scheduled_for=scheduled_for,
    )

    checking_after = banking_api_client.get_account(
        account_id=checking_before.id,
        access_token=funded_account.access_token,
    )
    savings_after = banking_api_client.get_account(
        account_id=savings_before.id,
        access_token=funded_account.access_token,
    )

    assert transfer.sender_user_id == registered_user.user.id
    assert transfer.recipient_user_id == registered_user.user.id
    assert transfer.source_account_id == checking_before.id
    assert transfer.destination_account_id == savings_before.id
    assert transfer.amount == "25.00"
    assert transfer.currency == "USD"
    assert transfer.status == "SCHEDULED"
    assert transfer.transfer_kind == "OWN_ACCOUNT"
    assert transfer.scheduled_for == scheduled_for
    assert transfer.completed_at is None
    assert (
        checking_after.settled_balance,
        checking_after.available_balance,
    ) == (
        checking_before.settled_balance,
        checking_before.available_balance,
    )
    assert (
        savings_after.settled_balance,
        savings_after.available_balance,
    ) == (
        savings_before.settled_balance,
        savings_before.available_balance,
    )


@pytest.mark.invariant
def test_scheduled_account_transfer_can_be_canceled_before_execution(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    savings_before = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=funded_account.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    scheduled_for = datetime.now(UTC).date() + timedelta(days=2)
    scheduled = banking_api_client.create_account_transfer(
        source_account_id=checking_before.id,
        destination_account_id=savings_before.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
        scheduled_for=scheduled_for,
    )

    canceled = banking_api_client.cancel_transfer(
        transfer_id=scheduled.id,
        access_token=funded_account.access_token,
    )
    retrieved = banking_api_client.get_transfer(
        transfer_id=scheduled.id,
        access_token=funded_account.access_token,
    )
    checking_after = banking_api_client.get_account(
        account_id=checking_before.id,
        access_token=funded_account.access_token,
    )
    savings_after = banking_api_client.get_account(
        account_id=savings_before.id,
        access_token=funded_account.access_token,
    )

    assert scheduled.status == "SCHEDULED"
    assert canceled.id == scheduled.id
    assert canceled.status == "CANCELED"
    assert canceled.scheduled_for == scheduled_for
    assert canceled.completed_at is not None
    assert retrieved.id == canceled.id
    assert retrieved.status == "CANCELED"
    assert retrieved.completed_at == canceled.completed_at
    assert (
        checking_after.settled_balance,
        checking_after.available_balance,
    ) == (
        checking_before.settled_balance,
        checking_before.available_balance,
    )
    assert (
        savings_after.settled_balance,
        savings_after.available_balance,
    ) == (
        savings_before.settled_balance,
        savings_before.available_balance,
    )


@pytest.mark.negative
@pytest.mark.invariant
def test_completed_account_transfer_cannot_be_canceled(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    savings = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=funded_account.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    posted = banking_api_client.create_account_transfer(
        source_account_id=funded_account.account.id,
        destination_account_id=savings.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    checking_before_rejection = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    savings_before_rejection = banking_api_client.get_account(
        account_id=savings.id,
        access_token=funded_account.access_token,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.cancel_transfer(
            transfer_id=posted.id,
            access_token=funded_account.access_token,
        )

    retrieved = banking_api_client.get_transfer(
        transfer_id=posted.id,
        access_token=funded_account.access_token,
    )
    checking_after_rejection = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    savings_after_rejection = banking_api_client.get_account(
        account_id=savings.id,
        access_token=funded_account.access_token,
    )
    error = exc_info.value

    assert error.status_code == 409
    assert error.error is not None
    assert error.error.error.code == "SCHEDULED_TRANSFER_NOT_CANCELABLE"
    assert retrieved.id == posted.id
    assert retrieved.status == "POSTED"
    assert retrieved.completed_at == posted.completed_at
    assert (
        checking_after_rejection.settled_balance,
        checking_after_rejection.available_balance,
    ) == (
        checking_before_rejection.settled_balance,
        checking_before_rejection.available_balance,
    )
    assert (
        savings_after_rejection.settled_balance,
        savings_after_rejection.available_balance,
    ) == (
        savings_before_rejection.settled_balance,
        savings_before_rejection.available_balance,
    )


@pytest.mark.negative
@pytest.mark.invariant
def test_own_account_transfer_rejects_same_source_and_destination(
    banking_api_client: BankingApiClient,
    funded_account,
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
    assert error.error is not None
    assert error.error.error.code == "OWN_ACCOUNT_TRANSFER_REQUIRES_DISTINCT_ACCOUNTS"
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
    funded_account,
) -> None:
    other_id = uuid4().hex
    other_email = f"api-test-user-{other_id}@example.com"
    other_password = f"Test-user-{other_id}"
    banking_api_client.register_user(
        email=other_email,
        display_name="Other Test User",
        password=other_password,
    )
    other_token = banking_api_client.login(
        email=other_email,
        password=other_password,
    )
    other_savings_before = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=other_token.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    owner_checking_before = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    owner_activity_before = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    other_activity_before = banking_api_client.list_activity(
        access_token=other_token.access_token,
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
        access_token=other_token.access_token,
    )
    owner_activity_after = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    other_activity_after = banking_api_client.list_activity(
        access_token=other_token.access_token,
        limit=100,
    )
    error = exc_info.value

    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "ACCOUNT_NOT_FOUND"
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
