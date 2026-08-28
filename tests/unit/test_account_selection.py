"""Unit tests for deterministic account selection."""

import uuid

import pytest

from totally_testable_banking_api_tests.account_selection import get_account_by_type
from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
)

pytestmark = pytest.mark.unit


def _account(account_id: int, account_type: ProductAccountType) -> AccountResponse:
    return AccountResponse.model_validate(
        {
            "id": str(uuid.UUID(int=account_id)),
            "account_type": account_type,
            "currency": "USD",
            "settled_balance": "0.00",
            "available_balance": "0.00",
        }
    )


def test_get_account_by_type_selects_requested_type_regardless_of_order() -> None:
    savings = _account(1, ProductAccountType.SAVINGS)
    checking = _account(2, ProductAccountType.CHECKING)

    selected = get_account_by_type(
        [savings, checking],
        ProductAccountType.CHECKING,
    )

    assert selected is checking


def test_get_account_by_type_rejects_missing_type() -> None:
    accounts = [_account(1, ProductAccountType.SAVINGS)]

    with pytest.raises(ValueError, match="exactly one CHECKING account, found 0"):
        get_account_by_type(accounts, ProductAccountType.CHECKING)


def test_get_account_by_type_rejects_duplicate_type() -> None:
    accounts = [
        _account(1, ProductAccountType.CHECKING),
        _account(2, ProductAccountType.CHECKING),
    ]

    with pytest.raises(ValueError, match="exactly one CHECKING account, found 2"):
        get_account_by_type(accounts, ProductAccountType.CHECKING)
