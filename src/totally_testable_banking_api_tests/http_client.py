import httpx


class ApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()
