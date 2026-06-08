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


SQUEUE_FORMAT = "%i|%P|%j|%u|%T|%M|%l|%m|%k"
SACCT_FORMAT = "JobID,NCPUS,Elapsed,CPUTime,ReqMem,MaxRSS"
SINFO_NODES_FORMAT = "%.20N %.10t %.6c %.10m %.20G"
SINFO_PARTITIONS_FORMAT = "%P %a %l %D %N"


def build_slurm_list_command(
    user: str | None = None,
    all_users: bool = False,
    states: Sequence[str] | None = None,
) -> list[str]:
    """Build the Slurm command that lists jobs."""
    command = ["squeue"]

    if not all_users:
        username = user if user is not None else getpass.getuser()
        if not username:
            raise ValueError("Could not determine the current username.")
        command.extend(["-u", username])

    if states:
        state_values = [state.strip() for state in states if state.strip()]
        if not state_values:
            raise ValueError("states must contain at least one non-empty string.")
        command.append(f"--states={','.join(state_values)}")

    command.extend(["--noheader", f"--format={SQUEUE_FORMAT}"])
    return command


def build_slurm_pending_command(user: str | None = None) -> list[str]:
    """Build the Slurm command that lists pending jobs for a user."""
    return build_slurm_list_command(user=user, states=["PENDING"])


def build_slurm_running_command(user: str | None = None) -> list[str]:
    """Build the Slurm command that lists running jobs for a user."""
    return build_slurm_list_command(user=user, states=["RUNNING"])


def build_slurm_job_command(job_id: str) -> list[str]:
    """Build the Slurm accounting command for *job_id*."""
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job id must be a non-empty string.")

    return [
        "sacct",
        "--parsable2",
        "--noheader",
        f"--format={SACCT_FORMAT}",
        "--units=G",
        "-j",
        job_id,
    ]


def build_info_nodes_command() -> list[str]:
    """Build the Slurm command that lists compute node information."""
    return [
        "sinfo",
        "-N",
        "-o",
        SINFO_NODES_FORMAT,
    ]


def build_info_partitions_command() -> list[str]:
    """Build the Slurm command that lists partition information."""
    return [
        "sinfo",
        "-o",
        SINFO_PARTITIONS_FORMAT,
    ]


def build_system_node_status_command(node_name: str) -> list[str]:
    """Build the Slurm command that shows detailed node status."""
    if not isinstance(node_name, str) or not node_name.strip():
        raise ValueError("node name must be a non-empty string.")

    return [
        "scontrol",
        "show",
        "node",
        node_name,
    ]


def build_system_partition_status_command(partition_name: str) -> list[str]:
    """Build the Slurm command that shows detailed partition status."""
    if not isinstance(partition_name, str) or not partition_name.strip():
        raise ValueError("partition name must be a non-empty string.")

    return [
        "scontrol",
        "show",
        "partition",
        partition_name,
    ]


def build_system_resources_command() -> list[str]:
    """Build the Slurm command that shows node resource allocation."""
    return ["scontrol", "show", "nodes"]


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


def capture_command_output(
    command: Sequence[str], stderr: TextIO | None = None
) -> tuple[int, str]:
    """Run a command list and return its exit code and captured stdout."""
    err = stderr if stderr is not None else sys.stderr
    executable = command[0] if command else "Slurm command"

    try:
        completed = subprocess.run(
            command,
            shell=False,
            check=False,
            stdout=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print(
            f"Error: '{executable}' was not found in PATH. "
            "Slurm commands are not available in this environment. "
            "Try running this on a Mjolnir login node or load the correct module.",
            file=err,
        )
        return 127, ""

    return completed.returncode, completed.stdout
