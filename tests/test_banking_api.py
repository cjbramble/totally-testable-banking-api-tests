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
