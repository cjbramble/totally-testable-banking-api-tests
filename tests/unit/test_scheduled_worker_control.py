"""Unit tests for bounded scheduled-worker command construction."""

import subprocess
import uuid
from datetime import date
from pathlib import Path

import pytest

from totally_testable_banking_api_tests.scheduled_worker_control import (
    ScheduledWorkerCommandError,
    ScheduledWorkerControl,
)

pytestmark = pytest.mark.unit


def test_process_due_transfer_targets_exact_operation_and_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transfer_id = uuid.UUID("00000000-0000-4000-8000-000000000001")
    captured_command: list[str] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_command.extend(command)
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 30.0,
        }
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    control = ScheduledWorkerControl(Path("/workspace/compose.yaml"))

    control.process_due_transfer(
        transfer_id=transfer_id,
        banking_date=date(2026, 8, 28),
    )

    assert captured_command == [
        "docker",
        "compose",
        "--file",
        "/workspace/compose.yaml",
        "run",
        "--rm",
        "--no-deps",
        "api",
        "banking-scheduled-worker",
        "process",
        "--transfer-id",
        str(transfer_id),
        "--as-of",
        "2026-08-28",
    ]


def test_process_due_transfer_exposes_bounded_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            2,
            stdout="",
            stderr="transfer was not found, not due, or no longer pending",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    control = ScheduledWorkerControl(Path("/workspace/compose.yaml"))

    with pytest.raises(ScheduledWorkerCommandError) as exc_info:
        control.process_due_transfer(
            transfer_id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
            banking_date=date(2026, 8, 28),
        )

    error = exc_info.value
    assert error.returncode == 2
    assert "not due" in str(error)
