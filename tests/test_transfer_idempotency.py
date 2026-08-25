import time
from decimal import Decimal
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.contract
@pytest.mark.invariant
def test_replayed_transfer_has_one_identity_and_one_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    sender_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    source_account = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]

    funding = banking_api_client.create_deposit(
        destination_account_id=source_account.id,
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
    destination_account = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]

    source_before = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=destination_account.id,
        access_token=recipient_token.access_token,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=recipient_token.access_token,
    ).items

    transfer_amount = Decimal("25.00")
    idempotency_key = f"transfer-{uuid4()}"
    first = banking_api_client.create_transfer(
        source_account_id=source_account.id,
        destination_account_id=destination_account.id,
        amount=str(transfer_amount),
        access_token=sender_token.access_token,
        idempotency_key=idempotency_key,
    )
    replay = banking_api_client.create_transfer(
        source_account_id=source_account.id,
        destination_account_id=destination_account.id,
        amount=str(transfer_amount),
        access_token=sender_token.access_token,
        idempotency_key=idempotency_key,
    )

    source_after = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=destination_account.id,
        access_token=recipient_token.access_token,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=recipient_token.access_token,
    ).items

    assert replay.id == first.id
    assert Decimal(source_after.settled_balance) == (
        Decimal(source_before.settled_balance) - transfer_amount
    )
    assert Decimal(source_after.available_balance) == (
        Decimal(source_before.available_balance) - transfer_amount
    )
    assert Decimal(destination_after.settled_balance) == (
        Decimal(destination_before.settled_balance) + transfer_amount
    )
    assert Decimal(destination_after.available_balance) == (
        Decimal(destination_before.available_balance) + transfer_amount
    )
    assert len(sender_activity_after) == len(sender_activity_before) + 1
    assert len(recipient_activity_after) == len(recipient_activity_before) + 1
    assert sum(item.operation_id == first.id for item in sender_activity_after) == 1
    assert sum(item.operation_id == first.id for item in recipient_activity_after) == 1
