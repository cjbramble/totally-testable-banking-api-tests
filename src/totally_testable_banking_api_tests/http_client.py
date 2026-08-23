from collections.abc import Mapping

import httpx
from pydantic import ValidationError

from totally_testable_banking_api_tests.error_models import ErrorResponse


class UnexpectedStatusError(RuntimeError):
    """Raised when an HTTP response has an unexpected status code."""

    def __init__(self, response: httpx.Response, *, method: str) -> None:
        self.method = method
        self.url = str(response.url)
        self.status_code = response.status_code
        self.content_type = response.headers.get("content-type", "")
        self.body = response.text[:500]
        try:
            self.error: ErrorResponse | None = ErrorResponse.model_validate_json(response.content)
        except (ValidationError, ValueError):
            self.error = None

        if self.error is not None:
            detail = f"code={self.error.error.code!r}; message={self.error.error.message!r}"
        else:
            detail = f"content-type={self.content_type!r}; body={self.body!r}"

        super().__init__(f"{method} {self.url} returned HTTP {self.status_code}; {detail}")


class ApiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int,
        headers: Mapping[str, str] | None = None,
        json_body: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        response = self._client.request(
            method,
            path,
            headers=headers,
            json=json_body,
        )

        if response.status_code != expected_status:
            raise UnexpectedStatusError(response, method=method)

        return response

    def close(self) -> None:
        self._client.close()
