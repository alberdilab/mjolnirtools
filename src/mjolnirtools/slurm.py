"""Slurm command construction and execution helpers."""

from __future__ import annotations

import getpass
import subprocess
import sys
from collections.abc import Sequence
from typing import TextIO


def validate_positive_integer(value: int, name: str) -> int:
    """Return *value* if it is positive, otherwise raise ValueError."""
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def validate_memory(value: str) -> str:
    """Return *value* if it is a non-empty memory string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("mem must be a non-empty string, for example 8G.")
    return value


def build_interactive_command(hours: int, cpus: int = 4, mem: str = "8G") -> list[str]:
    """Build the Slurm command for an interactive shell session."""
    validate_positive_integer(hours, "hours")
    validate_positive_integer(cpus, "cpus")
    validate_memory(mem)

    return [
        "srun",
        "--nodes=1",
        "--ntasks=1",
        f"--cpus-per-task={cpus}",
        f"--mem={mem}",
        f"--time={hours}:00:00",
        "--pty",
        "bash",
    ]


SQUEUE_FORMAT = "%.18i %.9P %.30j %.8u %.8T %.10M %.9l %.6m %k"
SACCT_FORMAT = "JobID,NCPUS,Elapsed,CPUTime,ReqMem,maxrss"


def build_slurm_list_command(user: str | None = None, all_users: bool = False) -> list[str]:
    """Build the Slurm command that lists jobs."""
    command = [
        "squeue",
        f"--format={SQUEUE_FORMAT}",
    ]

    if all_users:
        return command

    username = user if user is not None else getpass.getuser()
    if not username:
        raise ValueError("Could not determine the current username.")

    return ["squeue", "-u", username, f"--format={SQUEUE_FORMAT}"]


def build_slurm_job_command(job_id: str) -> list[str]:
    """Build the Slurm accounting command for *job_id*."""
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job id must be a non-empty string.")

    return [
        "sacct",
        f"--format={SACCT_FORMAT}",
        "--units=G",
        "-j",
        job_id,
    ]


def run_command(command: Sequence[str], stderr: TextIO | None = None) -> int:
    """Run a command list and return its exit code.

    Missing Slurm executables are handled here so normal users see a short,
    actionable error instead of a Python traceback.
    """
    err = stderr if stderr is not None else sys.stderr
    executable = command[0] if command else "Slurm command"

    try:
        completed = subprocess.run(command, shell=False, check=False)
    except FileNotFoundError:
        print(
            f"Error: '{executable}' was not found in PATH. "
            "Slurm commands are not available in this environment. "
            "Try running this on a Mjolnir login node or load the correct module.",
            file=err,
        )
        return 127

    return completed.returncode
