import httpx


class UnexpectedStatusError(RuntimeError):
    """Raised when an HTTP response has an unexpected status code."""

    def __init__(self, response: httpx.Response, *, method: str) -> None:
        self.method = method
        self.url = str(response.url)
        self.status_code = response.status_code
        self.content_type = response.headers.get("content-type", "")
        self.body = response.text[:500]

        super().__init__(
            f"{method} {self.url} returned HTTP {self.status_code}; "
            f"content-type={self.content_type!r}; body={self.body!r}"
        )


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
            raise UnexpectedStatusError(response, method=method)

        return response

    def close(self) -> None:
        self._client.close()
