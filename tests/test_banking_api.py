"""MockTransport tests for endpoint request construction and response parsing."""

import json
import uuid

import httpx
import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient


@pytest.mark.contract
def test_register_user_sends_registration_payload_and_parses_user_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/users"
        assert json.loads(request.content) == {
            "email": "new-user@example.com",
            "display_name": "New User",
            "password": "correct-horse-battery-staple",
        }
        return httpx.Response(
            201,
            json={
                "id": "00000000-0000-4000-8000-000000000001",
                "email": "new-user@example.com",
                "display_name": "New User",
                "created_at": "2026-08-23T12:00:00Z",
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = BankingApiClient(transport)

    try:
        user = client.register_user(
            email="new-user@example.com",
            display_name="New User",
            password="correct-horse-battery-staple",
        )
    finally:
        transport.close()

    assert str(user.id) == "00000000-0000-4000-8000-000000000001"
    assert user.email == "new-user@example.com"
    assert user.display_name == "New User"


@pytest.mark.contract
def test_login_parses_token_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/tokens"
        assert json.loads(request.content) == {
            "email": "alice@example.test",
            "password": "correct-horse-battery-staple",
        }
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "expires_in": 1800,
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = BankingApiClient(transport)

    try:
        token = client.login(
            email="alice@example.test",
            password="correct-horse-battery-staple",
        )
    finally:
        transport.close()

    assert token.access_token == "access-token"
    assert token.expires_in == 1800
    assert token.token_type == "bearer"


@pytest.mark.contract
def test_list_accounts_sends_bearer_token_and_parses_account_responses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/accounts"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "account_type": "CHECKING",
                    "currency": "USD",
                    "settled_balance": "1000.00",
                    "available_balance": "1000.00",
                },
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "account_type": "SAVINGS",
                    "currency": "USD",
                    "settled_balance": "2500.00",
                    "available_balance": "2500.00",
                },
            ],
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = BankingApiClient(transport)

    try:
        accounts = client.list_accounts(access_token="access-token")
    finally:
        transport.close()

    assert len(accounts) == 2
    assert accounts[0].account_type.value == "CHECKING"
    assert accounts[1].account_type.value == "SAVINGS"
    assert accounts[0].settled_balance == "1000.00"


@pytest.mark.contract
def test_create_transfer_sends_request_and_parses_transfer_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/transfers"
        assert request.headers["Authorization"] == "Bearer access-token"
        assert request.headers["Idempotency-Key"] == "transfer-key"
        assert json.loads(request.content) == {
            "source_account_id": "00000000-0000-0000-0000-000000000001",
            "destination_account_id": "00000000-0000-0000-0000-000000000002",
            "amount": "25.00",
        }
        return httpx.Response(
            201,
            json={
                "id": "00000000-0000-4000-8000-000000000003",
                "sender_user_id": "00000000-0000-4000-8000-000000000004",
                "recipient_user_id": "00000000-0000-4000-8000-000000000005",
                "source_account_id": "00000000-0000-0000-0000-000000000001",
                "destination_account_id": "00000000-0000-0000-0000-000000000002",
                "amount": "25.00",
                "currency": "USD",
                "status": "POSTED",
                "transfer_kind": "P2P",
                "created_at": "2026-08-23T12:00:00Z",
                "scheduled_for": None,
                "failure_code": None,
                "completed_at": "2026-08-23T12:00:00Z",
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = BankingApiClient(transport)

    try:
        transfer = client.create_transfer(
            source_account_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            destination_account_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            amount="25.00",
            access_token="access-token",
            idempotency_key="transfer-key",
        )
    finally:
        transport.close()

    assert str(transfer.id) == "00000000-0000-4000-8000-000000000003"
    assert transfer.amount == "25.00"
    assert transfer.transfer_kind == "P2P"


@pytest.mark.contract
def test_list_activity_sends_pagination_and_parses_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/activity"
        assert request.headers["Authorization"] == "Bearer access-token"
        assert request.url.params["limit"] == "2"
        assert request.url.params["cursor"] == "opaque-cursor"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "operation_id": "00000000-0000-4000-8000-000000000003",
                        "kind": "TRANSFER",
                        "direction": "SENT",
                        "account_id": "00000000-0000-0000-0000-000000000001",
                        "counterparty_user_id": "00000000-0000-4000-8000-000000000005",
                        "amount": "25.00",
                        "currency": "USD",
                        "status": "POSTED",
                        "failure_code": None,
                        "created_at": "2026-08-23T12:00:00Z",
                        "completed_at": "2026-08-23T12:00:00Z",
                        "scheduled_for": None,
                    }
                ],
                "next_cursor": "next-opaque-cursor",
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = BankingApiClient(transport)

    try:
        page = client.list_activity(
            access_token="access-token",
            limit=2,
            cursor="opaque-cursor",
        )
    finally:
        transport.close()

    assert len(page.items) == 1
    assert page.items[0].direction.value == "SENT"
    assert page.items[0].amount == "25.00"
    assert page.next_cursor == "next-opaque-cursor"


@pytest.mark.contract
def test_withdrawal_methods_send_published_requests_and_parse_responses() -> None:
    instruction_id = uuid.UUID("00000000-0000-4000-8000-000000000010")
    source_account_id = uuid.UUID("00000000-0000-4000-8000-000000000011")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer access-token"
        if request.method == "POST":
            assert request.url.path == "/api/v1/withdrawals"
            assert request.headers["Idempotency-Key"] == "withdrawal-key"
            assert json.loads(request.content) == {
                "source_account_id": str(source_account_id),
                "amount": "25.00",
            }
            status_code = 202
        else:
            assert request.method == "GET"
            assert request.url.path == f"/api/v1/withdrawals/{instruction_id}"
            status_code = 200

        return httpx.Response(
            status_code,
            json={
                "id": str(instruction_id),
                "source_account_id": str(source_account_id),
                "amount": "25.00",
                "currency": "USD",
                "status": "CREATED",
                "failure_code": None,
                "created_at": "2026-08-25T12:00:00Z",
                "completed_at": None,
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = BankingApiClient(transport)

    try:
        created = client.create_withdrawal(
            source_account_id=source_account_id,
            amount="25.00",
            access_token="access-token",
            idempotency_key="withdrawal-key",
        )
        retrieved = client.get_withdrawal(
            instruction_id=created.id,
            access_token="access-token",
        )
    finally:
        transport.close()

    assert created.id == instruction_id
    assert retrieved.id == created.id
    assert retrieved.source_account_id == source_account_id
