"""Account-selection helpers for tests that require one product account type."""

from collections.abc import Iterable

from totally_testable_banking_api_tests.api_models import (
    AccountResponse,
    ProductAccountType,
)


def get_account_by_type(
    accounts: Iterable[AccountResponse],
    account_type: ProductAccountType,
) -> AccountResponse:
    """Return the only account of the requested type."""

    matches = [account for account in accounts if account.account_type is account_type]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {account_type.value} account, found {len(matches)}")
    return matches[0]
