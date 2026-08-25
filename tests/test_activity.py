"""Two-party activity projection tests for completed financial operations."""

import time
from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.api_models import ActivityDirection, ActivityKind
from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.contract
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
