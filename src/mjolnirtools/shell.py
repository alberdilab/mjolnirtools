"""Local shell command construction and execution helpers."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from typing import TextIO


VALID_LIST_SORTS = ("name", "time", "size")
VALID_LIST_ORDERS = ("asc", "des")


def validate_screen_id(value: str) -> str:
    """Return *value* if it is a non-empty screen session id."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("screen id must be a non-empty string.")
    return value


def validate_conda_env_name(value: str) -> str:
    """Return *value* if it is a non-empty Conda environment name."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Conda environment name must be a non-empty string.")
    return value


def build_list_command(sort_by: str = "name", order: str | None = None) -> list[str]:
    """Build the local file listing command."""
    sort = sort_by.lower()
    if sort not in VALID_LIST_SORTS:
        raise ValueError("sort must be one of: name, time, size.")

    if order is not None and order not in VALID_LIST_ORDERS:
        raise ValueError("order must be one of: asc, des.")

    default_order = "asc" if sort == "name" else "des"
    selected_order = order if order is not None else default_order

    flags = "-lah"
    if sort == "time":
        flags += "t"
    elif sort == "size":
        flags += "S"

    if selected_order != default_order:
        flags += "r"

    return ["ls", flags]


def build_screen_attach_command(screen_id: str) -> list[str]:
    """Build the command that attaches to a screen session."""
    return ["screen", "-r", validate_screen_id(screen_id)]


def build_screen_list_command() -> list[str]:
    """Build the command that lists screen sessions."""
    return ["screen", "-ls"]


def build_screen_kill_command(screen_id: str) -> list[str]:
    """Build the command that quits a screen session."""
    return ["screen", "-S", validate_screen_id(screen_id), "-X", "quit"]


def build_conda_create_command(env_name: str) -> list[str]:
    """Build the command that creates a Conda environment."""
    return ["conda", "create", "--name", validate_conda_env_name(env_name)]


def build_conda_remove_command(env_name: str) -> list[str]:
    """Build the command that removes a Conda environment."""
    return ["conda", "env", "remove", "--name", validate_conda_env_name(env_name)]


def build_conda_list_command() -> list[str]:
    """Build the command that lists Conda environments."""
    return ["conda", "env", "list"]


def run_command(command: Sequence[str], stderr: TextIO | None = None) -> int:
    """Run a local command list and return its exit code."""
    err = stderr if stderr is not None else sys.stderr
    executable = command[0] if command else "command"

    try:
        completed = subprocess.run(command, shell=False, check=False)
    except FileNotFoundError:
        print(f"Error: '{executable}' was not found in PATH.", file=err)
        return 127

    return completed.returncode
