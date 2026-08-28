"""Live P2P atomic-balance and transfer-ownership tests."""

from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.account_selection import get_account_by_type
from totally_testable_banking_api_tests.api_models import ProductAccountType
from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserAuthenticator,
    UserRegistrar,
)
from totally_testable_banking_api_tests.test_data import RegisteredUser


@pytest.mark.invariant
def test_p2p_transfer_moves_exact_amount_between_accounts(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    sender = authenticate_user(registered_user)
    recipient = authenticate_user(
        register_user(display_name="Recipient Test User"),
    )

    create_settled_deposit(
        destination_account_id=sender.checking.id,
        access_token=sender.access_token,
    )

    sender_before = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=sender.access_token,
        ),
        ProductAccountType.CHECKING,
    )
    recipient_before = recipient.checking
    transfer_amount = Decimal("25.00")

    transfer = banking_api_client.create_transfer(
        source_account_id=sender_before.id,
        destination_account_id=recipient_before.id,
        amount=str(transfer_amount),
        access_token=sender.access_token,
        idempotency_key=f"transfer-{uuid4()}",
    )

    sender_after = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=sender.access_token,
        ),
        ProductAccountType.CHECKING,
    )
    recipient_after = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=recipient.access_token,
        ),
        ProductAccountType.CHECKING,
    )

    assert transfer.sender_user_id == sender.user.id
    assert transfer.recipient_user_id == recipient.user.id
    assert transfer.source_account_id == sender_before.id
    assert transfer.destination_account_id == recipient_before.id
    assert transfer.amount == "25.00"
    assert transfer.currency == "USD"
    assert transfer.status == "POSTED"
    assert transfer.transfer_kind == "P2P"
    assert transfer.completed_at is not None
    assert Decimal(sender_after.settled_balance) == (
        Decimal(sender_before.settled_balance) - transfer_amount
    )
    assert Decimal(recipient_after.settled_balance) == (
        Decimal(recipient_before.settled_balance) + transfer_amount
    )


@pytest.mark.negative
def test_outsider_cannot_retrieve_another_users_transfer(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    create_settled_deposit: SettledDepositCreator,
) -> None:
    owner_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    owner_account = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=owner_token.access_token,
        ),
        ProductAccountType.CHECKING,
    )

    recipient = register_user(display_name="Recipient Test User")
    recipient_token = banking_api_client.login(
        email=recipient.email,
        password=recipient.password,
    )
    recipient_account = get_account_by_type(
        banking_api_client.list_accounts(
            access_token=recipient_token.access_token,
        ),
        ProductAccountType.CHECKING,
    )

    create_settled_deposit(
        destination_account_id=owner_account.id,
        access_token=owner_token.access_token,
    )

    transfer = banking_api_client.create_transfer(
        source_account_id=owner_account.id,
        destination_account_id=recipient_account.id,
        amount="25.00",
        access_token=owner_token.access_token,
        idempotency_key=f"transfer-{uuid4()}",
    )

    outsider = register_user(display_name="Outsider Test User")
    outsider_token = banking_api_client.login(
        email=outsider.email,
        password=outsider.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.get_transfer(
            transfer_id=transfer.id,
            access_token=outsider_token.access_token,
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error_code == "TRANSFER_NOT_FOUND"
