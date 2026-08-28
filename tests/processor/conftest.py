"""Fixtures scoped to simulated-processor boundary tests."""

from collections.abc import Iterator

import pytest

from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.processor_control import ProcessorControlClient
from totally_testable_banking_api_tests.settings import load_settings


@pytest.fixture
def processor_control_client() -> Iterator[ProcessorControlClient]:
    """Provide an isolated client for the local simulated-processor boundary."""

    settings = load_settings()
    transport = ApiClient(
        base_url=settings.processor_control_url,
        timeout=settings.request_timeout_seconds,
    )

    try:
        yield ProcessorControlClient(
            transport,
            token=settings.processor_control_secret.get_secret_value(),
        )
    finally:
        transport.close()
