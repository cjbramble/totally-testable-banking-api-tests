"""Fixtures scoped to transfer behavior tests."""

import pytest

from totally_testable_banking_api_tests.scheduled_worker_control import (
    ScheduledWorkerControl,
)
from totally_testable_banking_api_tests.settings import load_settings


@pytest.fixture
def scheduled_worker_control() -> ScheduledWorkerControl:
    """Provide operation-scoped access to the local scheduled-transfer worker."""

    settings = load_settings()
    return ScheduledWorkerControl(settings.sut_compose_file)
