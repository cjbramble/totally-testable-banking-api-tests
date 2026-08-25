import enum
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProductAccountType(enum.StrEnum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"


class ActivityDirection(enum.StrEnum):
    SENT = "SENT"
    RECEIVED = "RECEIVED"
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class ActivityKind(enum.StrEnum):
    TRANSFER = "TRANSFER"
    ACCOUNT_TRANSFER = "ACCOUNT_TRANSFER"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    expires_in: int
    token_type: str = "bearer"


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expires_in: int


class AccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    account_type: ProductAccountType
    currency: str
    settled_balance: str
    available_balance: str


class DepositResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    destination_account_id: uuid.UUID
    amount: str
    currency: str
    status: str
    failure_code: str | None
    created_at: datetime
    completed_at: datetime | None


class TransferResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    sender_user_id: uuid.UUID
    recipient_user_id: uuid.UUID
    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID
    amount: str
    currency: str
    status: str
    transfer_kind: str
    created_at: datetime
    scheduled_for: date | None
    failure_code: str | None
    completed_at: datetime | None


class ActivityItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: uuid.UUID
    kind: ActivityKind
    direction: ActivityDirection
    account_id: uuid.UUID
    counterparty_user_id: uuid.UUID | None
    amount: str
    currency: str
    status: str
    failure_code: str | None
    created_at: datetime
    completed_at: datetime | None
    scheduled_for: date | None


class ActivityPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ActivityItemResponse]
    next_cursor: str | None


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime
