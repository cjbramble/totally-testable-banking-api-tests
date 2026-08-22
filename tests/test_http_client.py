import httpx
import pytest

from totally_testable_banking_api_tests.http_client import (
    ApiClient,
    UnexpectedStatusError,
)


def test_request_returns_response_when_status_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ready"}, request=request)

    client = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    try:
        response = client.request("GET", "/health", expected_status=200)
    finally:
        client.close()

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_request_raises_for_unexpected_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    try:
        with pytest.raises(
            UnexpectedStatusError,
            match=r"Expected HTTP 200, got 503",
        ):
            client.request("GET", "/health", expected_status=200)
    finally:
        client.close()
