from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient


@pytest.mark.contract
def test_owned_account_accepts_a_deposit_request(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]

    deposit = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )

    assert deposit.id
    assert deposit.destination_account_id == account.id
    assert deposit.amount == "100.00"
    assert deposit.currency == "USD"
    assert deposit.status == "CREATED"
    assert deposit.failure_code is None
    assert deposit.completed_at is None


@pytest.mark.contract
def test_created_deposit_can_be_retrieved_by_its_owner(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]
    deposit = banking_api_client.create_deposit(
        destination_account_id=account.id,
        amount="100.00",
        access_token=token.access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )

    retrieved = banking_api_client.get_deposit(
        instruction_id=deposit.id,
        access_token=token.access_token,
    )

    assert retrieved.id == deposit.id
    assert retrieved.destination_account_id == deposit.destination_account_id
    assert retrieved.status == "CREATED"
