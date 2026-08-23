import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.settings import load_settings


@pytest.mark.smoke
def test_default_local_settings_are_accepted(monkeypatch):
    monkeypatch.delenv("SUT_BASE_URL", raising=False)

    settings = load_settings(env_file=None)

    assert settings.sut_base_url == "http://127.0.0.1:8009"
    assert settings.request_timeout_seconds == 10.0


@pytest.mark.negative
def test_hosted_target_is_rejected(monkeypatch):
    monkeypatch.setenv("SUT_BASE_URL", "https://example.com")

    with pytest.raises(ValidationError, match="plain HTTP"):
        load_settings(env_file=None)


@pytest.mark.negative
def test_non_positive_timeout_is_rejected(monkeypatch):
    monkeypatch.delenv("SUT_BASE_URL", raising=False)
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        load_settings(env_file=None)


@pytest.mark.negative
def test_remote_http_target_is_rejected(monkeypatch):
    monkeypatch.setenv("SUT_BASE_URL", "http://example.com")

    with pytest.raises(
        ValidationError,
        match=r"localhost or 127\.0\.0\.1",
    ):
        load_settings(env_file=None)
