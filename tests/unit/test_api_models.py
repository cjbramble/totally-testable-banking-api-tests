"""Strict consumer-model tests derived from the published API contract."""

import uuid

import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
    TokenResponse,
    WithdrawalResponse,
)

pytestmark = pytest.mark.unit


def test_token_response_defaults_token_type_to_bearer() -> None:
    token = TokenResponse.model_validate({"access_token": "token-value", "expires_in": 1800})

    assert token.access_token == "token-value"
    assert token.expires_in == 1800
    assert token.token_type == "bearer"


def test_account_response_parses_uuid_and_account_type() -> None:
    account = AccountResponse.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "account_type": "CHECKING",
            "currency": "USD",
            "settled_balance": "1000.00",
            "available_balance": "1000.00",
        }
    )

    assert account.id == uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert account.account_type is ProductAccountType.CHECKING
    assert account.settled_balance == "1000.00"


def test_account_response_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        AccountResponse.model_validate(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "account_type": "CHECKING",
                "currency": "USD",
                "settled_balance": "1000.00",
                "available_balance": "1000.00",
                "owner_email": "undocumented@example.com",
            }
        )


def test_withdrawal_response_parses_published_fields() -> None:
    withdrawal = WithdrawalResponse.model_validate(
        {
            "id": "00000000-0000-4000-8000-000000000010",
            "source_account_id": "00000000-0000-4000-8000-000000000011",
            "amount": "25.00",
            "currency": "USD",
            "status": "CREATED",
            "failure_code": None,
            "created_at": "2026-08-25T12:00:00Z",
            "completed_at": None,
        }
    )

    assert withdrawal.id == uuid.UUID("00000000-0000-4000-8000-000000000010")
    assert withdrawal.source_account_id == uuid.UUID("00000000-0000-4000-8000-000000000011")
    assert withdrawal.amount == "25.00"
    assert withdrawal.created_at.tzinfo is not None
    assert withdrawal.completed_at is None


def test_withdrawal_response_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        WithdrawalResponse.model_validate(
            {
                "id": "00000000-0000-4000-8000-000000000010",
                "source_account_id": "00000000-0000-4000-8000-000000000011",
                "amount": "25.00",
                "currency": "USD",
                "status": "CREATED",
                "failure_code": None,
                "created_at": "2026-08-25T12:00:00Z",
                "completed_at": None,
                "processor_reference": "undocumented",
            }
        )
