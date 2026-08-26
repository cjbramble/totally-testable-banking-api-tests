"""Live P2P atomic-balance and transfer-ownership tests."""

import time
from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


@pytest.mark.invariant
def test_p2p_transfer_moves_exact_amount_between_accounts(
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
    recipient = banking_api_client.register_user(
        email=recipient_email,
        display_name="Recipient Test User",
        password=recipient_password,
    )
    recipient_token = banking_api_client.login(
        email=recipient_email,
        password=recipient_password,
    )

    funding = banking_api_client.create_deposit(
        destination_account_id=sender_account.id,
        amount="100.00",
        access_token=sender_token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    deadline = time.monotonic() + 10.0
    while True:
        current_funding = banking_api_client.get_deposit(
            instruction_id=funding.id,
            access_token=sender_token.access_token,
        )
        if current_funding.status == "SETTLED":
            break
        if current_funding.status == "FAILED":
            pytest.fail(f"Funding deposit failed with {current_funding.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(
                f"Funding deposit did not settle; final status was {current_funding.status!r}"
            )
        time.sleep(0.1)

    sender_before = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]
    recipient_before = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]
    transfer_amount = Decimal("25.00")

    transfer = banking_api_client.create_transfer(
        source_account_id=sender_before.id,
        destination_account_id=recipient_before.id,
        amount=str(transfer_amount),
        access_token=sender_token.access_token,
        idempotency_key=f"transfer-{uuid4()}",
    )

    sender_after = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]
    recipient_after = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]

    assert transfer.sender_user_id == registered_user.user.id
    assert transfer.recipient_user_id == recipient.id
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
    registered_user,
) -> None:
    owner_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    owner_account = banking_api_client.list_accounts(
        access_token=owner_token.access_token,
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
        destination_account_id=owner_account.id,
        amount="100.00",
        access_token=owner_token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    deadline = time.monotonic() + 10.0
    while True:
        current_funding = banking_api_client.get_deposit(
            instruction_id=funding.id,
            access_token=owner_token.access_token,
        )
        if current_funding.status == "SETTLED":
            break
        if current_funding.status == "FAILED":
            pytest.fail(f"Funding deposit failed with {current_funding.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(
                f"Funding deposit did not settle; final status was {current_funding.status!r}"
            )
        time.sleep(0.1)

    transfer = banking_api_client.create_transfer(
        source_account_id=owner_account.id,
        destination_account_id=recipient_account.id,
        amount="25.00",
        access_token=owner_token.access_token,
        idempotency_key=f"transfer-{uuid4()}",
    )

    outsider_id = uuid4().hex
    outsider_email = f"api-test-user-{outsider_id}@example.com"
    outsider_password = f"Test-user-{outsider_id}"
    banking_api_client.register_user(
        email=outsider_email,
        display_name="Outsider Test User",
        password=outsider_password,
    )
    outsider_token = banking_api_client.login(
        email=outsider_email,
        password=outsider_password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.get_transfer(
            transfer_id=transfer.id,
            access_token=outsider_token.access_token,
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "TRANSFER_NOT_FOUND"
