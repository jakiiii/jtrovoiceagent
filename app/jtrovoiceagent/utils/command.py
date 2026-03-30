from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_command(
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> CommandResult:
    completed = subprocess.run(
        list(args),
        env=dict(env) if env is not None else None,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=check,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
