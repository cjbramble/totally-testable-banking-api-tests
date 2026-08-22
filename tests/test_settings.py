import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.settings import load_settings


@pytest.mark.smoke
def test_default_local_settings_are_accepted(monkeypatch):
    monkeypatch.delenv("SUT_BASE_URL", raising=False)
    monkeypatch.setenv("TEST_SUPPORT_TOKEN", "local-token")

    settings = load_settings()

    assert settings.sut_base_url == "http://127.0.0.1:8009"
    assert settings.request_timeout_seconds == 10.0
    assert settings.test_support_token == "local-token"


@pytest.mark.negative
def test_hosted_target_is_rejected(monkeypatch):
    monkeypatch.setenv("SUT_BASE_URL", "https://example.com")
    monkeypatch.setenv("TEST_SUPPORT_TOKEN", "local-token")

    with pytest.raises(ValidationError):
        load_settings()
