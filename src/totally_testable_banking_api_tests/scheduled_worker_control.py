"""Bounded command adapter for the local scheduled-transfer worker."""

import subprocess
import uuid
from datetime import date
from pathlib import Path


class ScheduledWorkerCommandError(RuntimeError):
    """Raised when the exact scheduled-transfer worker command is refused."""

    def __init__(self, completed: subprocess.CompletedProcess[str]) -> None:
        self.returncode = completed.returncode
        self.stdout = completed.stdout[:1000]
        self.stderr = completed.stderr[:1000]
        detail = self.stderr.strip() or self.stdout.strip() or "no command output"
        super().__init__(f"Scheduled worker command exited with {self.returncode}: {detail}")


class ScheduledWorkerControl:
    """Run one operation-scoped worker action through the local SUT container."""

    def __init__(self, compose_file: Path, *, timeout_seconds: float = 30.0) -> None:
        self._compose_file = compose_file
        self._timeout_seconds = timeout_seconds

    def process_due_transfer(
        self,
        *,
        transfer_id: uuid.UUID,
        banking_date: date,
    ) -> None:
        command = [
            "docker",
            "compose",
            "--file",
            str(self._compose_file),
            "run",
            "--rm",
            "--no-deps",
            "api",
            "banking-scheduled-worker",
            "process",
            "--transfer-id",
            str(transfer_id),
            "--as-of",
            banking_date.isoformat(),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self._timeout_seconds,
        )
        if completed.returncode != 0:
            raise ScheduledWorkerCommandError(completed)
