import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.test_support_models import (
    CompleteRunRequest,
    CompletionOutcome,
    CompletionSummary,
    CreateRunRequest,
    CreateRunResponse,
    RunResponse,
)
from totally_testable_banking_api_tests.test_support_models import (
    TestRunStatus as RunStatus,
)


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

    assert request.suite.value == "API"
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
def test_complete_run_request_preserves_published_outcome_and_summary() -> None:
    request = CompleteRunRequest.model_validate(
        {
            "outcome": "PASSED",
            "summary": {"tests": 12, "failed": 0, "note": "All checks passed."},
        }
    )

    assert request.outcome is CompletionOutcome.PASSED
    assert request.summary == CompletionSummary(
        tests=12,
        failed=0,
        note="All checks passed.",
    )


@pytest.mark.contract
def test_complete_run_request_defaults_summary_to_none() -> None:
    request = CompleteRunRequest.model_validate({"outcome": "ABANDONED"})

    assert request.outcome is CompletionOutcome.ABANDONED
    assert request.summary is None


@pytest.mark.contract
def test_run_response_parses_terminal_status_and_observation_data() -> None:
    run = RunResponse.model_validate(
        {
            "run_id": "00000000-0000-0000-0000-000000000010",
            "external_name": "api-learning-run",
            "suite": "API",
            "worker_id": None,
            "status": "PASSED",
            "created_at": "2026-08-22T10:00:00Z",
            "expires_at": "2026-08-22T12:00:00Z",
            "completed_at": "2026-08-22T10:05:00Z",
            "completion_summary": {"tests": 12, "failed": 0, "note": "Passed."},
            "users": {
                "alice": {
                    "user_id": "00000000-0000-0000-0000-000000000011",
                    "email": "alice@example.com",
                    "checking_account_id": "00000000-0000-0000-0000-000000000012",
                    "savings_account_id": "00000000-0000-0000-0000-000000000013",
                }
            },
            "counts": {"users": 1, "funding_journals": 2, "transfers": 0},
        }
    )

    assert run.status is RunStatus.PASSED
    assert run.completed_at is not None
    assert run.completion_summary is not None
    assert run.completion_summary.failed == 0
    assert run.users["alice"].checking_account_id == uuid.UUID(
        "00000000-0000-0000-0000-000000000012"
    )
    assert run.counts.funding_journals == 2


@pytest.mark.contract
def test_run_response_rejects_undocumented_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        RunResponse.model_validate(
            {
                "run_id": "00000000-0000-0000-0000-000000000010",
                "external_name": "api-learning-run",
                "suite": "API",
                "worker_id": None,
                "status": "ACTIVE",
                "created_at": "2026-08-22T10:00:00Z",
                "expires_at": "2026-08-22T12:00:00Z",
                "completed_at": None,
                "completion_summary": None,
                "users": {},
                "counts": {"users": 0, "funding_journals": 0, "transfers": 0},
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
