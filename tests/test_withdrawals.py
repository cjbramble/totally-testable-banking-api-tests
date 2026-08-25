"""Live withdrawal acceptance and lifecycle tests."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


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


@pytest.mark.contract
def test_created_withdrawal_can_be_retrieved_by_its_owner(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=funded_account.account.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
    )

    retrieved = banking_api_client.get_withdrawal(
        instruction_id=withdrawal.id,
        access_token=funded_account.access_token,
    )

    assert retrieved.id == withdrawal.id
    assert retrieved.source_account_id == withdrawal.source_account_id
    assert retrieved.amount == withdrawal.amount
    assert retrieved.currency == withdrawal.currency
    assert retrieved.created_at == withdrawal.created_at


@pytest.mark.contract
@pytest.mark.negative
def test_outsider_cannot_retrieve_another_users_withdrawal(
    banking_api_client: BankingApiClient,
    funded_account,
) -> None:
    withdrawal = banking_api_client.create_withdrawal(
        source_account_id=funded_account.account.id,
        amount="25.00",
        access_token=funded_account.access_token,
        idempotency_key=f"withdrawal-{uuid4()}",
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
        banking_api_client.get_withdrawal(
            instruction_id=withdrawal.id,
            access_token=outsider_token.access_token,
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "WITHDRAWAL_NOT_FOUND"
