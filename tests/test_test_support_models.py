import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.test_support_models import (
    CreateRunRequest,
    CreateRunResponse,
)
from totally_testable_banking_api_tests.test_support_models import TestRunSuite as RunSuite


@pytest.mark.contract
def test_create_run_request_uses_published_defaults() -> None:
    request = CreateRunRequest.model_validate(
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

    assert request.suite is RunSuite.API
    assert request.fixture_template == "STANDARD_P2P"
    assert request.ttl_minutes == 120
    assert request.worker_id is None
    assert [user.alias for user in request.users] == ["alice", "bob"]


@pytest.mark.contract
def test_create_run_request_rejects_undocumented_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CreateRunRequest.model_validate(
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
                "database_url": "forbidden",
            }
        )


@pytest.mark.contract
def test_create_run_response_parses_generated_user_and_run_types() -> None:
    run = CreateRunResponse.model_validate(
        {
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
        }
    )

    assert run.run_id == uuid.UUID("00000000-0000-0000-0000-000000000010")
    assert run.expires_at == datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    assert run.users["alice"].checking_account_id == uuid.UUID(
        "00000000-0000-0000-0000-000000000012"
    )


@pytest.mark.contract
def test_create_run_response_rejects_undocumented_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CreateRunResponse.model_validate(
            {
                "run_id": "00000000-0000-0000-0000-000000000010",
                "run_token": "run-token",
                "expires_at": "2026-08-22T12:00:00Z",
                "users": {},
                "database_url": "forbidden",
            }
        )
