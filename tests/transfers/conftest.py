"""Fixtures scoped to transfer behavior tests."""

import pytest

from totally_testable_banking_api_tests.banking_api import BankingApiClient
from totally_testable_banking_api_tests.scheduled_worker_control import (
    ScheduledWorkerControl,
)
from totally_testable_banking_api_tests.settings import load_settings
from totally_testable_banking_api_tests.setup_actions import (
    SettledDepositCreator,
    UserAuthenticator,
    UserRegistrar,
)
from totally_testable_banking_api_tests.test_data import (
    FundedTransferContext,
    RegisteredUser,
)


@pytest.fixture
def funded_transfer_context(
    banking_api_client: BankingApiClient,
    registered_user: RegisteredUser,
    register_user: UserRegistrar,
    authenticate_user: UserAuthenticator,
    create_settled_deposit: SettledDepositCreator,
) -> FundedTransferContext:
    """Create fresh participants with a settled sender balance for each test."""

    sender = authenticate_user(registered_user)
    create_settled_deposit(
        destination_account_id=sender.checking.id,
        access_token=sender.access_token,
    )
    recipient = authenticate_user(
        register_user(display_name="Recipient Test User"),
    )

    return FundedTransferContext(
        sender_access_token=sender.access_token,
        recipient_access_token=recipient.access_token,
        source_account=sender.checking,
        destination_account=recipient.checking,
    )


@pytest.fixture
def scheduled_worker_control() -> ScheduledWorkerControl:
    """Provide operation-scoped access to the local scheduled-transfer worker."""

    settings = load_settings()
    return ScheduledWorkerControl(settings.sut_compose_file)
