"""Fixtures scoped to activity behavior tests."""

import pytest

from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserAuthenticator,
)
from totally_testable_banking_api_tests.test_data import (
    ActivityUserFunder,
    FundedActivityUser,
    RegisteredUser,
)


@pytest.fixture
def fund_activity_user(
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> ActivityUserFunder:
    """Authenticate a user and fund checking for activity assertions."""

    def fund(registered_user: RegisteredUser) -> FundedActivityUser:
        authenticated = authenticate_user(registered_user)
        deposit = create_settled_deposit(
            destination_account_id=authenticated.checking.id,
            access_token=authenticated.access_token,
        )
        return FundedActivityUser(
            access_token=authenticated.access_token,
            checking=authenticated.checking,
            savings=authenticated.savings,
            deposit_id=deposit.id,
        )

    return fund
