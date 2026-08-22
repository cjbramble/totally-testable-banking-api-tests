from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    sut_base_url: str = "http://127.0.0.1:8009"
    test_support_token: str
    request_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="forbid",
    )

    @field_validator("sut_base_url")
    @classmethod
    def validate_sut_base_url(cls, value: str) -> str:
        parsed = urlparse(value)

        if parsed.scheme != "http":
            raise ValueError("SUT_BASE_URL must use plain HTTP")

        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("SUT_BASE_URL must target localhost or 127.0.0.1")

        return value

    @field_validator("test_support_token")
    @classmethod
    def validate_test_support_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("TEST_SUPPORT_TOKEN must not be blank")

        return value

    @field_validator("request_timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be positive")

        return value


def load_settings(*, env_file: str | None = ".env") -> Settings:
    return Settings(_env_file=env_file)  # pyright: ignore[reportCallIssue]
