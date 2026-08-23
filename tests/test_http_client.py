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


def test_request_sends_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"status": "ready"}, request=request)

    client = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    try:
        response = client.request(
            "GET",
            "/health",
            expected_status=200,
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        client.close()

    assert response.status_code == 200


def test_request_raises_for_unexpected_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            text="service unavailable",
            headers={"content-type": "text/plain"},
            request=request,
        )

    client = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    try:
        with pytest.raises(UnexpectedStatusError) as exc_info:
            client.request("GET", "/health", expected_status=200)
    finally:
        client.close()

    error = exc_info.value
    assert error.method == "GET"
    assert error.url == "http://127.0.0.1:8009/health"
    assert error.status_code == 503
    assert error.content_type == "text/plain"
    assert error.body == "service unavailable"


def test_request_parses_published_error_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "INSUFFICIENT_FUNDS",
                    "message": "Available balance is insufficient.",
                }
            },
            request=request,
        )

    client = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    try:
        with pytest.raises(UnexpectedStatusError) as exc_info:
            client.request("POST", "/api/v1/transfers", expected_status=201)
    finally:
        client.close()

    error = exc_info.value
    assert error.error is not None
    assert error.error.error.code == "INSUFFICIENT_FUNDS"
    assert error.error.error.message == "Available balance is insufficient."
    assert "code='INSUFFICIENT_FUNDS'" in str(error)


def test_request_retains_diagnostics_for_malformed_error_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            text="not-json",
            headers={"content-type": "application/json"},
            request=request,
        )

    client = ApiClient(
        base_url="http://127.0.0.1:8009",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    try:
        with pytest.raises(UnexpectedStatusError) as exc_info:
            client.request("GET", "/health/ready", expected_status=200)
    finally:
        client.close()

    error = exc_info.value
    assert error.error is None
    assert error.body == "not-json"
    assert "body='not-json'" in str(error)
