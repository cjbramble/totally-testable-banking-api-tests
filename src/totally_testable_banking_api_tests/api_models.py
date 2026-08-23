import enum
import uuid

from pydantic import BaseModel, ConfigDict


class ProductAccountType(enum.StrEnum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    expires_in: int
    token_type: str = "bearer"


class AccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    account_type: ProductAccountType
    currency: str
    settled_balance: str
    available_balance: str
