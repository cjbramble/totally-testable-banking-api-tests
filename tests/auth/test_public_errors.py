"""Live authentication-error evidence for unauthenticated API access."""

import pytest

from totally_testable_banking_api_tests.http_client import (
    ApiClient,
    UnexpectedStatusError,
)
from totally_testable_banking_api_tests.settings import load_settings


@pytest.mark.negative
def test_unauthenticated_accounts_request_returns_authentication_error() -> None:
    settings = load_settings()
    client = ApiClient(
        base_url=settings.sut_base_url,
        timeout=settings.request_timeout_seconds,
    )

    try:
        with pytest.raises(UnexpectedStatusError) as exc_info:
            client.request("GET", "/api/v1/accounts", expected_status=200)
    finally:
        client.close()

    error = exc_info.value
    assert error.status_code == 401
    assert error.error is not None
    assert error.error.error.code == "AUTHENTICATION_REQUIRED"
    assert error.error.error.message
