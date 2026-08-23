import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.test_support_client import (
    TestSupportClient as SupportClient,
)
from totally_testable_banking_api_tests.test_support_models import (
    CreateRunRequest,
)


@pytest.mark.contract
def test_create_run_sends_control_plane_token_and_returns_typed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/runs"
        assert request.headers["Authorization"] == "Bearer support-token"
        assert json.loads(request.content) == {
            "external_name": "api-learning-run",
            "suite": "API",
            "fixture_template": "STANDARD_P2P",
            "users": [
                {
                    "alias": "alice",
                    "checking_balance": "1000.00",
                    "savings_balance": "500.00",
                },
                {
                    "alias": "bob",
                    "checking_balance": "1000.00",
                    "savings_balance": "500.00",
                },
            ],
            "ttl_minutes": 120,
        }
        return httpx.Response(
            201,
            json={
                "run_id": "00000000-0000-0000-0000-000000000010",
                "run_token": "run-token",
                "expires_at": "2026-08-22T12:00:00Z",
                "users": {
                    "alice": {
                        "user_id": "00000000-0000-0000-0000-000000000011",
                        "email": "alice@example.com",
                        "password": "password-value",
                        "checking_account_id": "00000000-0000-0000-0000-000000000012",
                        "savings_account_id": "00000000-0000-0000-0000-000000000013",
                    }
                },
            },
            request=request,
        )

    transport = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client = SupportClient(transport, token="support-token")
    run_request = CreateRunRequest.model_validate(
        {
            "external_name": "api-learning-run",
            "suite": "API",
            "fixture_template": "STANDARD_P2P",
            "users": [
                {
                    "alias": "alice",
                    "checking_balance": "1000.00",
                    "savings_balance": "500.00",
                },
                {
                    "alias": "bob",
                    "checking_balance": "1000.00",
                    "savings_balance": "500.00",
                },
            ],
        }
    )

    try:
        run = client.create_run(run_request)
    finally:
        transport.close()

    assert run.run_id == uuid.UUID("00000000-0000-0000-0000-000000000010")
    assert run.expires_at == datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    assert run.users["alice"].email == "alice@example.com"
