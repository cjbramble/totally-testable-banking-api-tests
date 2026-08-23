import json

import httpx
import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import ApiClient


@pytest.mark.contract
def test_login_returns_typed_token_response() -> None:
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
def test_list_accounts_sends_bearer_token_and_returns_typed_accounts() -> None:
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
