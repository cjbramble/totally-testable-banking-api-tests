import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.settings import load_settings


@pytest.mark.negative
def test_hosted_target_is_rejected(monkeypatch):
    monkeypatch.setenv("SUT_BASE_URL", "https://example.com")
    monkeypatch.setenv("TEST_SUPPORT_TOKEN", "local-token")

    with pytest.raises(ValidationError):
        load_settings()
