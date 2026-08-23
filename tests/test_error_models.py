import pytest
from pydantic import ValidationError

from totally_testable_banking_api_tests.error_models import ErrorResponse


@pytest.mark.contract
def test_error_response_accepts_published_envelope() -> None:
    response = ErrorResponse.model_validate(
        {
            "error": {
                "code": "INSUFFICIENT_FUNDS",
                "message": "Available balance is insufficient.",
            }
        }
    )

    assert response.error.code == "INSUFFICIENT_FUNDS"
    assert response.error.message == "Available balance is insufficient."


@pytest.mark.contract
def test_error_response_rejects_undocumented_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ErrorResponse.model_validate(
            {
                "error": {
                    "code": "INSUFFICIENT_FUNDS",
                    "message": "Available balance is insufficient.",
                    "debug": "internal detail",
                }
            }
        )
