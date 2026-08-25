"""Live withdrawal acceptance and lifecycle tests."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.contract
def test_withdrawal_request_for_owned_account_is_accepted(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=funded_account.account.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
    )

    assert withdrawal.id
    assert withdrawal.source_account_id == funded_account.account.id
    assert withdrawal.amount == "25.00"
    assert withdrawal.currency == "USD"
    assert withdrawal.status == "CREATED"
    assert withdrawal.failure_code is None
    assert withdrawal.completed_at is None
