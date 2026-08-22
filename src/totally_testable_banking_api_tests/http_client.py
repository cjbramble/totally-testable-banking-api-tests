import httpx


class UnexpectedStatusError(RuntimeError):
    """Raised when an HTTP response has an unexpected status code."""


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
    ) -> httpx.Response:
        response = self._client.request(method, path)

        if response.status_code != expected_status:
            raise UnexpectedStatusError(
                f"Expected HTTP {expected_status}, got {response.status_code}"
            )

        return response

    def close(self) -> None:
        self._client.close()
