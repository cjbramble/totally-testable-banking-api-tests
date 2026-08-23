import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.test_support_models import CreateRunResponse


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
