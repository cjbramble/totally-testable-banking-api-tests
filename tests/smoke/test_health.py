"""Live smoke evidence that the local API reports readiness."""

import pytest

from totally_testable_banking_api_tests.http_client import ApiClient
from totally_testable_banking_api_tests.settings import load_settings


@pytest.mark.smoke
def test_readiness_endpoint_returns_documented_response() -> None:
    settings = load_settings()
    client = ApiClient(
        base_url=settings.sut_base_url,
        timeout=settings.request_timeout_seconds,
    )

    try:
        response = client.request("GET", "/health/ready", expected_status=200)
    finally:
        client.close()

    body = response.json()

    assert isinstance(body, dict)
    assert all(isinstance(key, str) for key in body)
    assert all(isinstance(value, str) for value in body.values())
