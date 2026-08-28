"""Live own-account transfer lifecycle and financial-invariant tests."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
    TransferResponse,
)
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.operation_polling import wait_for_terminal_status
from totally_testable_banking_api_tests.scheduled_worker_control import (
    ScheduledWorkerCommandError,
    ScheduledWorkerControl,
)
from totally_testable_banking_api_tests.setup_actions import UserRegistrar
from totally_testable_banking_api_tests.test_data import FundedAccount, RegisteredUser


@dataclass(frozen=True)
class _AuthenticatedAccounts:
    access_token: str
    checking: AccountResponse
    savings: AccountResponse


def _register_authenticated_user(
    banking_api_client: BankingApiClient,
    register_user: UserRegistrar,
) -> _AuthenticatedAccounts:
    user = register_user(display_name="Other Test User")
    token = banking_api_client.login(email=user.email, password=user.password)
    accounts = banking_api_client.list_accounts(access_token=token.access_token)
    return _AuthenticatedAccounts(
        access_token=token.access_token,
        checking=next(
            account for account in accounts if account.account_type is ProductAccountType.CHECKING
        ),
        savings=next(
            account for account in accounts if account.account_type is ProductAccountType.SAVINGS
        ),
    )


def _wait_for_transfer_terminal(
    banking_api_client: BankingApiClient,
    *,
    transfer_id: UUID,
    access_token: str,
) -> TransferResponse:
    return wait_for_terminal_status(
        lambda: banking_api_client.get_transfer(
            transfer_id=transfer_id,
            access_token=access_token,
        ),
        operation_name="scheduled transfer",
        terminal_statuses={"POSTED", "FAILED"},
    )


@pytest.mark.invariant
def test_immediate_checking_to_savings_transfer_moves_exact_amount(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    funded_account: FundedAccount,
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
    registered_user: RegisteredUser,
    funded_account: FundedAccount,
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
    registered_user: RegisteredUser,
    funded_account: FundedAccount,
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
    funded_account: FundedAccount,
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
    funded_account: FundedAccount,
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
    funded_account: FundedAccount,
    register_user: UserRegistrar,
) -> None:
    other_user = _register_authenticated_user(banking_api_client, register_user)
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


@pytest.mark.negative
@pytest.mark.invariant
def test_own_account_transfer_rejects_foreign_source(
    banking_api_client: BankingApiClient,
    funded_account: FundedAccount,
    register_user: UserRegistrar,
) -> None:
    other_user = _register_authenticated_user(banking_api_client, register_user)
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


@pytest.mark.negative
@pytest.mark.invariant
@pytest.mark.parametrize(
    "day_offset",
    [-1, 0],
    ids=["past", "today"],
)
def test_scheduled_account_transfer_rejects_non_future_date(
    banking_api_client: BankingApiClient,
    funded_account: FundedAccount,
    day_offset: int,
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
    activity_before = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    banking_date = datetime.now(ZoneInfo("America/New_York")).date()
    scheduled_for = banking_date + timedelta(days=day_offset)

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_account_transfer(
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
    activity_after = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    error = exc_info.value

    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == "SCHEDULED_DATE_MUST_BE_FUTURE"
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
    assert [item.operation_id for item in activity_after.items] == [
        item.operation_id for item in activity_before.items
    ]


@pytest.mark.invariant
def test_scheduled_account_transfer_posts_on_controlled_banking_date(
    banking_api_client: BankingApiClient,
    scheduled_worker_control: ScheduledWorkerControl,
    funded_account: FundedAccount,
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
    scheduled_for = datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=2)
    transfer_amount = Decimal("25.00")
    scheduled = banking_api_client.create_account_transfer(
        source_account_id=checking_before.id,
        destination_account_id=savings_before.id,
        amount=str(transfer_amount),
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
        scheduled_for=scheduled_for,
    )

    scheduled_worker_control.process_due_transfer(
        transfer_id=scheduled.id,
        banking_date=scheduled_for,
    )
    posted = _wait_for_transfer_terminal(
        banking_api_client,
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

    assert posted.status == "POSTED"
    assert posted.scheduled_for == scheduled_for
    assert posted.completed_at is not None
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

    with pytest.raises(ScheduledWorkerCommandError) as exc_info:
        scheduled_worker_control.process_due_transfer(
            transfer_id=scheduled.id,
            banking_date=scheduled_for,
        )

    checking_after_retry = banking_api_client.get_account(
        account_id=checking_before.id,
        access_token=funded_account.access_token,
    )
    savings_after_retry = banking_api_client.get_account(
        account_id=savings_before.id,
        access_token=funded_account.access_token,
    )
    activity = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    matching_activity = [item for item in activity.items if item.operation_id == scheduled.id]

    assert exc_info.value.returncode == 2
    assert (
        checking_after_retry.settled_balance,
        checking_after_retry.available_balance,
    ) == (
        checking_after.settled_balance,
        checking_after.available_balance,
    )
    assert (
        savings_after_retry.settled_balance,
        savings_after_retry.available_balance,
    ) == (
        savings_after.settled_balance,
        savings_after.available_balance,
    )
    assert len(matching_activity) == 1
    assert matching_activity[0].status == "POSTED"


@pytest.mark.negative
@pytest.mark.invariant
def test_scheduled_account_transfer_fails_when_funds_are_spent_before_execution(
    banking_api_client: BankingApiClient,
    scheduled_worker_control: ScheduledWorkerControl,
    funded_account: FundedAccount,
) -> None:
    savings = next(
        account
        for account in banking_api_client.list_accounts(
            access_token=funded_account.access_token,
        )
        if account.account_type is ProductAccountType.SAVINGS
    )
    checking = banking_api_client.get_account(
        account_id=funded_account.account.id,
        access_token=funded_account.access_token,
    )
    scheduled_for = datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=2)
    scheduled = banking_api_client.create_account_transfer(
        source_account_id=checking.id,
        destination_account_id=savings.id,
        amount="80.00",
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
        scheduled_for=scheduled_for,
    )
    banking_api_client.create_account_transfer(
        source_account_id=checking.id,
        destination_account_id=savings.id,
        amount="30.00",
        access_token=funded_account.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    checking_before_execution = banking_api_client.get_account(
        account_id=checking.id,
        access_token=funded_account.access_token,
    )
    savings_before_execution = banking_api_client.get_account(
        account_id=savings.id,
        access_token=funded_account.access_token,
    )

    scheduled_worker_control.process_due_transfer(
        transfer_id=scheduled.id,
        banking_date=scheduled_for,
    )
    failed = _wait_for_transfer_terminal(
        banking_api_client,
        transfer_id=scheduled.id,
        access_token=funded_account.access_token,
    )
    checking_after_execution = banking_api_client.get_account(
        account_id=checking.id,
        access_token=funded_account.access_token,
    )
    savings_after_execution = banking_api_client.get_account(
        account_id=savings.id,
        access_token=funded_account.access_token,
    )
    activity = banking_api_client.list_activity(
        access_token=funded_account.access_token,
        limit=100,
    )
    matching_activity = [item for item in activity.items if item.operation_id == scheduled.id]

    assert failed.status == "FAILED"
    assert failed.failure_code == "INSUFFICIENT_FUNDS"
    assert failed.scheduled_for == scheduled_for
    assert failed.completed_at is not None
    assert (
        checking_after_execution.settled_balance,
        checking_after_execution.available_balance,
    ) == (
        checking_before_execution.settled_balance,
        checking_before_execution.available_balance,
    )
    assert (
        savings_after_execution.settled_balance,
        savings_after_execution.available_balance,
    ) == (
        savings_before_execution.settled_balance,
        savings_before_execution.available_balance,
    )
    assert len(matching_activity) == 1
    assert matching_activity[0].status == "FAILED"
    assert matching_activity[0].failure_code == "INSUFFICIENT_FUNDS"
