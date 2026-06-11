"""Local shell command construction and execution helpers."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from typing import TextIO


VALID_LIST_SORTS = ("name", "time", "size")
VALID_LIST_ORDERS = ("asc", "des")
VALID_PERMISSION_ACTIONS = ("exec", "open", "private", "shared", "fix")


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


def build_permissions_exec_command(path: str, recursive: bool) -> list[list[str]]:
    """Build the command(s) that make a path executable."""
    if recursive:
        return [["find", path, "-exec", "chmod", "+x", "{}", "+"]]
    return [["chmod", "+x", path]]


def build_permissions_open_command(
    path: str, recursive: bool, is_dir: bool
) -> list[list[str]]:
    """Build the command(s) that open permissions (755 dirs, 644 files)."""
    if recursive:
        return [
            ["find", path, "-type", "d", "-exec", "chmod", "755", "{}", "+"],
            ["find", path, "-type", "f", "-exec", "chmod", "644", "{}", "+"],
        ]
    return [["chmod", "755" if is_dir else "644", path]]


def build_permissions_private_command(
    path: str, recursive: bool, is_dir: bool
) -> list[list[str]]:
    """Build the command(s) that restrict permissions to owner only (700 dirs, 600 files)."""
    if recursive:
        return [
            ["find", path, "-type", "d", "-exec", "chmod", "700", "{}", "+"],
            ["find", path, "-type", "f", "-exec", "chmod", "600", "{}", "+"],
        ]
    return [["chmod", "700" if is_dir else "600", path]]


def build_permissions_shared_command(
    path: str, recursive: bool, is_dir: bool
) -> list[list[str]]:
    """Build the command(s) that set group-writable permissions with setgid inheritance."""
    if recursive:
        return [
            ["find", path, "-type", "d", "-exec", "chmod", "775", "{}", "+"],
            ["find", path, "-type", "d", "-exec", "chmod", "g+s", "{}", "+"],
            ["find", path, "-type", "f", "-exec", "chmod", "664", "{}", "+"],
        ]
    if is_dir:
        return [["chmod", "775", path], ["chmod", "g+s", path]]
    return [["chmod", "664", path]]


def build_permissions_fix_command(
    path: str, recursive: bool, is_dir: bool
) -> list[list[str]]:
    """Build the command(s) that reset permissions to safe defaults (755 dirs, 644 files)."""
    if recursive:
        return [
            ["find", path, "-type", "d", "-exec", "chmod", "755", "{}", "+"],
            ["find", path, "-type", "f", "-exec", "chmod", "644", "{}", "+"],
        ]
    return [["chmod", "755" if is_dir else "644", path]]


PEOPLE_BASE = "/projects/alberdilab/people"
SCRATCH_BASE = "/projects/alberdilab/scratch"


def derive_scratch_destination(source: str) -> str:
    """Compute the scratch destination path for a given people source path."""
    src = source.rstrip("/")
    prefix = PEOPLE_BASE + "/"
    if not src.startswith(prefix):
        raise ValueError(
            f"Source must be a path under {PEOPLE_BASE}/, "
            f"for example {PEOPLE_BASE}/username/project."
        )
    return SCRATCH_BASE + src[len(PEOPLE_BASE):]


def is_inside_screen() -> bool:
    """Return True if the process is running inside a GNU Screen session."""
    return bool(os.environ.get("STY"))


def build_move_scratch_script(src: str, dest: str, keep_original: bool) -> str:
    """Build the bash script string for the rsync-based move operation."""
    dest_parent = dest.rsplit("/", 1)[0]

    def q(s: str) -> str:
        return '"' + s.replace('"', '\\"') + '"'

    sync_part = (
        f"mkdir -p {q(dest_parent)} && "
        f"rsync -avh --info=progress2 {q(src)} {q(dest_parent)}/"
    )
    if keep_original:
        return sync_part + " && echo 'Transfer complete. Source kept.'"
    return (
        f"if {sync_part}; then "
        f"rm -rf {q(src)} && echo 'Transfer complete. Source deleted.'; "
        f"else echo 'ERROR: Transfer failed. Source was NOT deleted.'; fi"
    )


def build_move_scratch_screen_command(session_name: str, script: str) -> list[str]:
    """Build the screen command that runs a transfer in a new detached session."""
    return ["screen", "-dmS", session_name, "bash", "-c", script]


def run_commands(commands: list[list[str]]) -> int:
    """Run a sequence of command lists, stopping at the first non-zero exit code."""
    for command in commands:
        exit_code = run_command(command)
        if exit_code != 0:
            return exit_code
    return 0


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
