"""Activity pagination input validation behavior."""

from uuid import uuid4

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.http_client import UnexpectedStatusError
from totally_testable_banking_api_tests.test_data import (
    ActivityUserFunder,
    RegisteredUser,
)


@pytest.mark.negative
def test_malformed_activity_cursor_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.list_activity(
            access_token=token.access_token,
            cursor="not-a-valid-cursor",
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error_code == "INVALID_CURSOR"


@pytest.mark.negative
def test_altered_activity_cursor_is_rejected(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    fund_activity_user: ActivityUserFunder,
) -> None:
    activity_user = fund_activity_user(registered_user)
    banking_api_client.create_account_transfer(
        source_account_id=activity_user.checking.id,
        destination_account_id=activity_user.savings.id,
        amount="25.00",
        access_token=activity_user.access_token,
        idempotency_key=f"account-transfer-{uuid4()}",
    )
    first_page = banking_api_client.list_activity(
        access_token=activity_user.access_token,
        limit=1,
    )
    cursor = first_page.next_cursor
    assert cursor is not None

    mutation_index = len(cursor) // 2
    replacement = "A" if cursor[mutation_index] != "A" else "B"
    altered_cursor = cursor[:mutation_index] + replacement + cursor[mutation_index + 1 :]

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.list_activity(
            access_token=activity_user.access_token,
            cursor=altered_cursor,
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error_code == "INVALID_CURSOR"


@pytest.mark.parametrize(
    "limit",
    [1, 100],
    ids=["minimum", "maximum"],
)
def test_activity_limit_accepts_documented_boundaries(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    limit: int,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )

    page = banking_api_client.list_activity(
        access_token=token.access_token,
        limit=limit,
    )

    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.negative
@pytest.mark.parametrize(
    "limit",
    [0, 101],
    ids=["below-minimum", "above-maximum"],
)
def test_activity_limit_rejects_values_outside_documented_range(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    limit: int,
) -> None:
    token = banking_api_client.login(
        email=registered_user.email,
        password=registered_user.password,
    )

    with pytest.raises(UnexpectedStatusError) as exc_info:
        banking_api_client.list_activity(
            access_token=token.access_token,
            limit=limit,
        )

    error = exc_info.value
    assert error.status_code == 422
    assert error.error_code == "VALIDATION_ERROR"
