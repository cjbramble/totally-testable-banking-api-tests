"""Transfer rejection tests proving stable errors and no financial side effects."""

import time
from uuid import UUID, uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError


def _fund_account_and_wait_for_settlement(
    banking_api_client: BankingApiClient,
    *,
    account_id: UUID,
    access_token: str,
    amount: str = "100.00",
) -> None:
    """Create the viable settled balance required by rejection scenarios."""

    funding = banking_api_client.create_deposit(
        destination_account_id=account_id,
        amount=amount,
        access_token=access_token,
        idempotency_key=f"deposit-{uuid4()}",
    )
    deadline = time.monotonic() + 10.0
    while True:
        current_funding = banking_api_client.get_deposit(
            instruction_id=funding.id,
            access_token=access_token,
        )
        if current_funding.status == "SETTLED":
            return
        if current_funding.status == "FAILED":
            pytest.fail(f"Funding deposit failed with {current_funding.failure_code!r}")
        if time.monotonic() >= deadline:
            pytest.fail(
                f"Funding deposit did not settle; final status was {current_funding.status!r}"
            )
        time.sleep(0.1)


@pytest.mark.contract
@pytest.mark.negative
@pytest.mark.parametrize(
    ("amount", "expected_error_code"),
    [
        pytest.param("0.00", "INVALID_AMOUNT", id="zero"),
        pytest.param("-1.00", "INVALID_AMOUNT", id="negative"),
        pytest.param("1.001", "INVALID_AMOUNT", id="over-precision"),
        pytest.param(
            "100000000000000000000.00",
            "VALIDATION_ERROR",
            id="oversized",
        ),
    ],
)
def test_invalid_amount_transfer_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
    amount: str,
    expected_error_code: str,
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

    sender_before = (sender_account.settled_balance, sender_account.available_balance)
    recipient_before = (
        recipient_account.settled_balance,
        recipient_account.available_balance,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=recipient_token.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender_account.id,
            destination_account_id=recipient_account.id,
            amount=amount,
            access_token=sender_token.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == expected_error_code

    sender_after = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]
    recipient_after = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]
    sender_activity_after = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=recipient_token.access_token,
    ).items
    assert (sender_after.settled_balance, sender_after.available_balance) == sender_before
    assert (
        recipient_after.settled_balance,
        recipient_after.available_balance,
    ) == recipient_before
    assert sender_activity_after == sender_activity_before
    assert recipient_activity_after == recipient_activity_before


@pytest.mark.contract
@pytest.mark.negative
@pytest.mark.parametrize(
    ("idempotency_key", "expected_error_code"),
    [
        pytest.param(None, "IDEMPOTENCY_KEY_REQUIRED", id="missing"),
        pytest.param("", "IDEMPOTENCY_KEY_INVALID", id="empty"),
        pytest.param("transfer key", "IDEMPOTENCY_KEY_INVALID", id="malformed"),
        pytest.param("k" * 129, "IDEMPOTENCY_KEY_INVALID", id="oversized"),
    ],
)
def test_invalid_idempotency_key_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
    idempotency_key: str | None,
    expected_error_code: str,
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

    sender_before = (sender_account.settled_balance, sender_account.available_balance)
    recipient_before = (
        recipient_account.settled_balance,
        recipient_account.available_balance,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=recipient_token.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=sender_account.id,
            destination_account_id=recipient_account.id,
            amount="1.00",
            access_token=sender_token.access_token,
            idempotency_key=idempotency_key,
        )

    error = exc_info.value
    assert error.status_code == 400
    assert error.error is not None
    assert error.error.error.code == expected_error_code

    sender_after = banking_api_client.list_accounts(
        access_token=sender_token.access_token,
    )[0]
    recipient_after = banking_api_client.list_accounts(
        access_token=recipient_token.access_token,
    )[0]
    sender_activity_after = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=recipient_token.access_token,
    ).items
    assert (sender_after.settled_balance, sender_after.available_balance) == sender_before
    assert (
        recipient_after.settled_balance,
        recipient_after.available_balance,
    ) == recipient_before
    assert sender_activity_after == sender_activity_before
    assert recipient_activity_after == recipient_activity_before


@pytest.mark.contract
@pytest.mark.negative
def test_foreign_source_account_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    owner_token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    source_account = banking_api_client.list_accounts(
        access_token=owner_token.access_token,
    )[0]

    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=source_account.id,
        access_token=owner_token.access_token,
    )

    actor_id = uuid4().hex
    actor_email = f"api-test-user-{actor_id}@example.com"
    actor_password = f"Test-user-{actor_id}"
    banking_api_client.register_user(
        email=actor_email,
        display_name="Actor Test User",
        password=actor_password,
    )
    actor_token = banking_api_client.login(
        email=actor_email,
        password=actor_password,
    )
    destination_account = banking_api_client.list_accounts(
        access_token=actor_token.access_token,
    )[0]

    source_before = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=owner_token.access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=destination_account.id,
        access_token=actor_token.access_token,
    )
    owner_activity_before = banking_api_client.list_activity(
        access_token=owner_token.access_token,
    ).items
    actor_activity_before = banking_api_client.list_activity(
        access_token=actor_token.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            amount="25.00",
            access_token=actor_token.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "ACCOUNT_NOT_FOUND"

    source_after = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=owner_token.access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=destination_account.id,
        access_token=actor_token.access_token,
    )
    owner_activity_after = banking_api_client.list_activity(
        access_token=owner_token.access_token,
    ).items
    actor_activity_after = banking_api_client.list_activity(
        access_token=actor_token.access_token,
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


@pytest.mark.contract
@pytest.mark.negative
def test_unknown_destination_account_is_rejected_without_financial_effect(
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
    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )

    source_before = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=source_account.id,
            destination_account_id=uuid4(),
            amount="25.00",
            access_token=sender_token.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 404
    assert error.error is not None
    assert error.error.error.code == "RECIPIENT_ACCOUNT_NOT_FOUND"

    source_after = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items

    assert (
        source_after.settled_balance,
        source_after.available_balance,
    ) == (
        source_before.settled_balance,
        source_before.available_balance,
    )
    assert activity_after == activity_before


@pytest.mark.contract
@pytest.mark.negative
def test_self_transfer_is_rejected_without_financial_effect(
    banking_api_client: BankingApiClient,
    registered_user,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )
    account = banking_api_client.list_accounts(access_token=token.access_token)[0]
    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=account.id,
        access_token=token.access_token,
    )

    account_before = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=token.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=account.id,
            destination_account_id=account.id,
            amount="25.00",
            access_token=token.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == "P2P_REQUIRES_DIFFERENT_USERS"

    account_after = banking_api_client.get_account(
        account_id=account.id,
        access_token=token.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=token.access_token,
    ).items

    assert (
        account_after.settled_balance,
        account_after.available_balance,
    ) == (
        account_before.settled_balance,
        account_before.available_balance,
    )
    assert activity_after == activity_before


@pytest.mark.contract
@pytest.mark.negative
def test_transfer_exceeding_available_balance_is_rejected_without_financial_effect(
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
    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=source_account.id,
        access_token=sender_token.access_token,
        amount="10.00",
    )

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

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=source_account.id,
            destination_account_id=destination_account.id,
            amount="25.00",
            access_token=sender_token.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 409
    assert error.error is not None
    assert error.error.error.code == "INSUFFICIENT_FUNDS"

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


@pytest.mark.contract
@pytest.mark.negative
def test_transfer_missing_destination_is_rejected_without_financial_effect(
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
    _fund_account_and_wait_for_settlement(
        banking_api_client,
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )

    source_before = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )
    activity_before = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer_from_payload(
            payload={
                "source_account_id": str(source_account.id),
                "amount": "25.00",
            },
            access_token=sender_token.access_token,
            idempotency_key=f"transfer-{uuid4()}",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error is not None
    assert error.error.error.code == "VALIDATION_ERROR"

    source_after = banking_api_client.get_account(
        account_id=source_account.id,
        access_token=sender_token.access_token,
    )
    activity_after = banking_api_client.list_activity(
        access_token=sender_token.access_token,
    ).items

    assert (
        source_after.settled_balance,
        source_after.available_balance,
    ) == (
        source_before.settled_balance,
        source_before.available_balance,
    )
    assert activity_after == activity_before
