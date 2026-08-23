import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FixtureUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    email: str
    password: str
    checking_account_id: uuid.UUID
    savings_account_id: uuid.UUID


class CreateRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    run_token: str
    expires_at: datetime
    users: dict[str, FixtureUserResponse]
