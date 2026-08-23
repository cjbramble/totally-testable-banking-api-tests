import uuid

import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
    TokenResponse,
)


@pytest.mark.contract
def test_token_response_uses_published_defaults() -> None:
    token = TokenResponse.model_validate({"access_token": "token-value", "expires_in": 1800})

    assert token.access_token == "token-value"
    assert token.expires_in == 1800
    assert token.token_type == "bearer"


@pytest.mark.contract
def test_account_response_parses_published_types() -> None:
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


@pytest.mark.contract
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
