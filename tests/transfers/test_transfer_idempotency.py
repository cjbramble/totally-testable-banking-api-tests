"""Transfer idempotency replay, conflict, and response-loss recovery."""

from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient, UnexpectedStatusError
from totally_testable_banking_api_tests.settings import load_settings
from totally_testable_banking_api_tests.test_data import FundedTransferContext


class LostSuccessfulResponseTransport(httpx.BaseTransport):
    """Forward a real request, then hide its successful response from the client."""

    def __init__(self, *, expected_status: int) -> None:
        self._transport = httpx.HTTPTransport()
        self._expected_status = expected_status

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._transport.handle_request(request)
        response.read()
        if response.status_code != self._expected_status:
            return response

        # The server completed the request; only its response is lost.
        response.close()
        raise httpx.ReadTimeout("Simulated lost successful response", request=request)

    def close(self) -> None:
        self._transport.close()


@pytest.mark.invariant
def test_replayed_transfer_has_one_identity_and_one_financial_effect(
    banking_api_client: BankingApiClient,
    funded_transfer_context: FundedTransferContext,
) -> None:
    context = funded_transfer_context
    source_before = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    transfer_amount = Decimal("25.00")
    idempotency_key = f"transfer-{uuid4()}"
    first = banking_api_client.create_transfer(
        source_account_id=context.source_account.id,
        destination_account_id=context.destination_account.id,
        amount=str(transfer_amount),
        access_token=context.sender_access_token,
        idempotency_key=idempotency_key,
    )
    replay = banking_api_client.create_transfer(
        source_account_id=context.source_account.id,
        destination_account_id=context.destination_account.id,
        amount=str(transfer_amount),
        access_token=context.sender_access_token,
        idempotency_key=idempotency_key,
    )

    source_after = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
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


@pytest.mark.negative
def test_changed_payload_with_reused_key_is_rejected_without_additional_effect(
    banking_api_client: BankingApiClient,
    funded_transfer_context: FundedTransferContext,
) -> None:
    context = funded_transfer_context
    idempotency_key = f"transfer-{uuid4()}"
    first = banking_api_client.create_transfer(
        source_account_id=context.source_account.id,
        destination_account_id=context.destination_account.id,
        amount="25.00",
        access_token=context.sender_access_token,
        idempotency_key=idempotency_key,
    )

    source_after_first = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_after_first = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_after_first = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_after_first = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.create_transfer(
            source_account_id=context.source_account.id,
            destination_account_id=context.destination_account.id,
            amount="30.00",
            access_token=context.sender_access_token,
            idempotency_key=idempotency_key,
        )

    error = exc_info.value
    assert error.status_code == 409
    assert error.error_code == "IDEMPOTENCY_PAYLOAD_MISMATCH"

    source_after_rejection = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_after_rejection = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_after_rejection = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_after_rejection = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    assert (
        source_after_rejection.settled_balance,
        source_after_rejection.available_balance,
    ) == (
        source_after_first.settled_balance,
        source_after_first.available_balance,
    )
    assert (
        destination_after_rejection.settled_balance,
        destination_after_rejection.available_balance,
    ) == (
        destination_after_first.settled_balance,
        destination_after_first.available_balance,
    )
    assert sender_activity_after_rejection == sender_activity_after_first
    assert recipient_activity_after_rejection == recipient_activity_after_first
    assert sum(item.operation_id == first.id for item in sender_activity_after_rejection) == 1
    assert sum(item.operation_id == first.id for item in recipient_activity_after_rejection) == 1


@pytest.mark.invariant
def test_retry_after_lost_response_recovers_one_transfer_effect(
    banking_api_client: BankingApiClient,
    funded_transfer_context: FundedTransferContext,
) -> None:
    context = funded_transfer_context
    source_before = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_before = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_before = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_before = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

    settings = load_settings()
    lost_response_transport = ApiClient(
        base_url=settings.sut_base_url,
        timeout=settings.request_timeout_seconds,
        transport=LostSuccessfulResponseTransport(expected_status=201),
    )
    uncertain_client = BankingApiClient(lost_response_transport)
    transfer_amount = Decimal("25.00")
    idempotency_key = f"ambiguous-transfer-{uuid4()}"

    try:
        with pytest.raises(httpx.ReadTimeout, match="Simulated lost successful response"):
            uncertain_client.create_transfer(
                source_account_id=context.source_account.id,
                destination_account_id=context.destination_account.id,
                amount=str(transfer_amount),
                access_token=context.sender_access_token,
                idempotency_key=idempotency_key,
            )
    finally:
        lost_response_transport.close()

    recovered = banking_api_client.create_transfer(
        source_account_id=context.source_account.id,
        destination_account_id=context.destination_account.id,
        amount=str(transfer_amount),
        access_token=context.sender_access_token,
        idempotency_key=idempotency_key,
    )

    source_after = banking_api_client.get_account(
        account_id=context.source_account.id,
        access_token=context.sender_access_token,
    )
    destination_after = banking_api_client.get_account(
        account_id=context.destination_account.id,
        access_token=context.recipient_access_token,
    )
    sender_activity_after = banking_api_client.list_activity(
        access_token=context.sender_access_token,
    ).items
    recipient_activity_after = banking_api_client.list_activity(
        access_token=context.recipient_access_token,
    ).items

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
    assert sum(item.operation_id == recovered.id for item in sender_activity_after) == 1
    assert sum(item.operation_id == recovered.id for item in recipient_activity_after) == 1
