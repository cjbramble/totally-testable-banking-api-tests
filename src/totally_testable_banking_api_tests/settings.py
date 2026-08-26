from urllib.parse import urlparse

from pydantic import SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    sut_base_url: str = "http://127.0.0.1:8009"
    processor_control_url: str = "http://127.0.0.1:8011"
    processor_control_secret: SecretStr
    request_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="forbid",
    )

    @field_validator("sut_base_url", "processor_control_url")
    @classmethod
    def validate_local_url(cls, value: str, info: ValidationInfo) -> str:
        parsed = urlparse(value)
        if info.field_name is None:
            raise ValueError("Local URL setting name is unavailable")
        setting_name = info.field_name.upper()

        if parsed.scheme != "http":
            raise ValueError(f"{setting_name} must use plain HTTP")

        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError(f"{setting_name} must target localhost or 127.0.0.1")

        return value

    @field_validator("processor_control_secret")
    @classmethod
    def validate_processor_control_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("PROCESSOR_CONTROL_SECRET must not be empty")

        return value

    @field_validator("request_timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be positive")

        return value


def load_settings(*, env_file: str | None = ".env") -> Settings:
    return Settings(_env_file=env_file)  # pyright: ignore[reportCallIssue]
