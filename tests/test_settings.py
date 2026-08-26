"""Configuration tests enforcing safe local targets and valid timeouts."""

import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.settings import load_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def processor_control_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSOR_CONTROL_SECRET", "test-processor-control-secret")


@pytest.mark.smoke
def test_default_local_settings_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUT_BASE_URL", raising=False)
    monkeypatch.delenv("PROCESSOR_CONTROL_URL", raising=False)

    settings = load_settings(env_file=None)

    assert settings.sut_base_url == "http://127.0.0.1:8009"
    assert settings.sut_compose_file.name == "compose.yaml"
    assert settings.sut_compose_file.parent.name == "totally-testable-banking"
    assert settings.processor_control_url == "http://127.0.0.1:8011"
    assert settings.processor_control_secret.get_secret_value() == "test-processor-control-secret"
    assert settings.request_timeout_seconds == 10.0


@pytest.mark.negative
def test_hosted_target_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUT_BASE_URL", "https://example.com")

    with pytest.raises(ValidationError, match="plain HTTP"):
        load_settings(env_file=None)


@pytest.mark.negative
def test_non_positive_timeout_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUT_BASE_URL", raising=False)
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        load_settings(env_file=None)


@pytest.mark.negative
def test_remote_http_target_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUT_BASE_URL", "http://example.com")

    with pytest.raises(
        ValidationError,
        match=r"localhost or 127\.0\.0\.1",
    ):
        load_settings(env_file=None)


@pytest.mark.negative
def test_remote_processor_control_target_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROCESSOR_CONTROL_URL", "http://processor.example.com")

    with pytest.raises(
        ValidationError,
        match=r"PROCESSOR_CONTROL_URL must target localhost or 127\.0\.0\.1",
    ):
        load_settings(env_file=None)


@pytest.mark.negative
def test_missing_processor_control_secret_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROCESSOR_CONTROL_SECRET")

    with pytest.raises(ValidationError, match="processor_control_secret"):
        load_settings(env_file=None)


@pytest.mark.negative
def test_missing_sut_compose_file_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUT_COMPOSE_FILE", "/path/that/does/not/exist/compose.yaml")

    with pytest.raises(ValidationError, match="local Compose file"):
        load_settings(env_file=None)
