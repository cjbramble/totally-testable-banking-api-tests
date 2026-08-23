import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TestRunSuite(StrEnum):
    API = "API"
    UI = "UI"
    CONCURRENCY = "CONCURRENCY"
    DATA_GENERATION = "DATA_GENERATION"
    MANUAL_DEMO = "MANUAL_DEMO"


class FixtureUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(pattern=r"^[a-z][a-z0-9-]{0,29}$")
    checking_balance: str = Field(max_length=20)
    savings_balance: str = Field(max_length=20)


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    suite: TestRunSuite
    fixture_template: Literal["STANDARD_P2P"]
    users: list[FixtureUserRequest] = Field(min_length=2, max_length=5)
    ttl_minutes: int = Field(default=120, ge=15, le=240)
    worker_id: str | None = Field(
        default=None,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )


class CompletionOutcome(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class CompletionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tests: int = Field(ge=0, le=1_000_000)
    failed: int = Field(ge=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=500)


class CompleteRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: CompletionOutcome
    summary: CompletionSummary | None = None


class TestRunStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"
    EXPIRED = "EXPIRED"


class RunCountsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    users: int
    funding_journals: int
    transfers: int


class RunUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    email: str
    checking_account_id: uuid.UUID
    savings_account_id: uuid.UUID


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    external_name: str
    suite: TestRunSuite
    worker_id: str | None
    status: TestRunStatus
    created_at: datetime
    expires_at: datetime
    completed_at: datetime | None
    completion_summary: CompletionSummary | None
    users: dict[str, RunUserResponse]
    counts: RunCountsResponse


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
