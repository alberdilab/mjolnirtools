"""Local shell command construction and execution helpers."""

from __future__ import annotations

import getpass
import glob as _glob
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
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


def build_list_command(
    sort_by: str = "name",
    order: str | None = None,
    path: str = ".",
    match: str | None = None,
) -> list[str]:
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

    if match is not None:
        pattern = os.path.join(path, match)
        matched = sorted(_glob.glob(pattern))
        if not matched:
            return []
        return ["ls", flags] + matched

    cmd = ["ls", flags]
    if path != ".":
        cmd.append(path)
    return cmd


def run_list_filtered(
    command: list[str],
    head: int | None = None,
    dirs_only: bool = False,
    files_only: bool = False,
) -> int:
    """Run a listing command with optional Python-side filtering and output limiting."""
    if not command:
        print("No files matched.", file=sys.stderr)
        return 1

    if head is None and not dirs_only and not files_only:
        return run_command(command)

    executable = command[0]
    try:
        result = subprocess.run(
            command,
            shell=False,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print(f"Error: '{executable}' not found in PATH.", file=sys.stderr)
        return 127

    if result.stderr:
        sys.stderr.write(result.stderr)

    lines = result.stdout.splitlines(keepends=True)
    header = [ln for ln in lines if ln.startswith("total ")]
    entries = [ln for ln in lines if not ln.startswith("total ")]

    if dirs_only:
        entries = [ln for ln in entries if ln.startswith("d")]
    elif files_only:
        entries = [ln for ln in entries if ln.startswith("-")]

    if head is not None:
        entries = entries[:head]

    for line in header + entries:
        sys.stdout.write(line)

    return result.returncode


def build_list_old_command(path: str = ".", days: int = 30) -> list[str]:
    """Build the find command for files not modified in the given number of days."""
    if days < 1:
        raise ValueError("days must be at least 1.")
    return ["find", path, "-type", "f", "-mtime", f"+{days}"]


def _parse_human_size(size_str: str) -> float:
    """Convert a human-readable size like '1.5G' to bytes for comparison."""
    s = size_str.strip().upper()
    if not s:
        return 0.0
    suffixes = {"K": 1024.0, "M": 1024.0 ** 2, "G": 1024.0 ** 3, "T": 1024.0 ** 4}
    if s[-1] in suffixes:
        try:
            return float(s[:-1]) * suffixes[s[-1]]
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def run_list_big(path: str = ".", head: int | None = None) -> int:
    """Run disk usage summary for immediate children of path, sorted by size descending."""
    cmd = ["du", "-h", "-d", "1", path]
    try:
        result = subprocess.run(
            cmd,
            shell=False,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print("Error: 'du' not found in PATH.", file=sys.stderr)
        return 127

    if result.stderr:
        sys.stderr.write(result.stderr)

    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    entries = sorted(
        lines,
        key=lambda ln: _parse_human_size(ln.split("\t", 1)[0]),
        reverse=True,
    )

    if head is not None:
        entries = entries[:head]

    for line in entries:
        print(line)

    return result.returncode


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


def build_conda_export_command(
    env_name: str, from_history: bool = False
) -> list[str]:
    """Build the command that exports a Conda environment specification."""
    command = ["conda", "env", "export", "--name", validate_conda_env_name(env_name)]
    if from_history:
        command.append("--from-history")
    return command


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

PROJECTS_ROOT = "/projects"
HOME_ROOT = "/home"
DEFAULT_PROJECT = "alberdilab"
VALID_CD_TARGETS = ("scratch", "people", "project", "data", "home")


def resolve_project(cwd: str | None = None) -> str:
    """Return the project id derived from *cwd*, or the default project.

    A working directory under ``/projects/<id>/...`` yields ``<id>``; anything
    else (for example a home directory) falls back to ``DEFAULT_PROJECT``.
    """
    raw = cwd if cwd is not None else os.getcwd()
    parts = Path(raw).parts
    if len(parts) >= 3 and parts[0] == os.sep and parts[1] == "projects":
        return parts[2]
    return DEFAULT_PROJECT


def resolve_user(user: str | None = None) -> str:
    """Return *user* if given, otherwise the current login user."""
    if user:
        return user
    name = os.environ.get("USER") or os.environ.get("LOGNAME")
    if name:
        return name
    return getpass.getuser()


def build_cd_path(
    target: str,
    project: str,
    user: str,
    is_dir: Callable[[str], bool] = os.path.isdir,
) -> str:
    """Resolve a ``mt cd`` *target* to an absolute path for the given context.

    ``scratch`` resolves to the user's personal scratch directory when it
    exists, falling back to the shared project scratch directory otherwise.
    """
    name = target.lower()
    if name == "home":
        return f"{HOME_ROOT}/{user}"

    project_root = f"{PROJECTS_ROOT}/{project}"
    if name == "people":
        return f"{project_root}/people"
    if name == "project":
        return f"{project_root}/people/{user}"
    if name == "data":
        return f"{project_root}/data"
    if name == "scratch":
        user_scratch = f"{project_root}/scratch/{user}"
        if is_dir(user_scratch):
            return user_scratch
        return f"{project_root}/scratch"

    raise ValueError(
        "Target must be one of: scratch, people, project, data, home."
    )


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


def build_move_erda_script(src: str, erda_dest: str, keep_original: bool) -> str:
    """Build the bash script string for the rsync-based move to ERDA."""
    def q(s: str) -> str:
        return '"' + s.replace('"', '\\"') + '"'

    remote_target = f"erda:{erda_dest}"
    sync_part = (
        f"ssh erda mkdir -p {q(erda_dest)} && "
        f"rsync -avh --info=progress2 {q(src)} {q(remote_target)}/"
    )
    if keep_original:
        return sync_part + " && echo 'Transfer complete. Source kept.'"
    return (
        f"if {sync_part}; then "
        f"rm -rf {q(src)} && echo 'Transfer complete. Source deleted.'; "
        f"else echo 'ERROR: Transfer failed. Source was NOT deleted.'; fi"
    )


def build_transfer_ena_script(src: str, keep_original: bool) -> str:
    """Build the bash script string for the FTPS-based upload to ENA Webin."""
    def q(s: str) -> str:
        return '"' + s.replace('"', '\\"') + '"'

    creds = str(Path.home() / ".config" / "ena" / "credentials")
    ftp_host = "webin2.ebi.ac.uk"

    # Credentials are read at runtime so the password never appears as a
    # literal argument in the process table.
    upload_block = "\n".join([
        f'ENA_USER=$(grep "^username=" {q(creds)} | cut -d= -f2-)',
        f'ENA_PASS=$(grep "^password=" {q(creds)} | cut -d= -f2-)',
        f'SRC={q(src)}',
        "UPLOAD_RC=1",
        'if [ -f "$SRC" ]; then',
        f'  curl --ftp-ssl -T "$SRC" "ftp://{ftp_host}/" --user "$ENA_USER:$ENA_PASS" --progress-bar',
        "  UPLOAD_RC=$?",
        'elif [ -d "$SRC" ]; then',
        "  UPLOAD_RC=0",
        '  while IFS= read -r -d "" file; do',
        '    rel="${file#"$SRC"/}"',
        f'    curl --ftp-ssl -T "$file" "ftp://{ftp_host}/${{rel}}" --user "$ENA_USER:$ENA_PASS" --progress-bar --create-dirs',
        "    RC=$?; [ $RC -ne 0 ] && UPLOAD_RC=$RC",
        "  done < <(find \"$SRC\" -type f -print0)",
        "else",
        '  echo "ERROR: Source not found: $SRC"',
        "  exit 1",
        "fi",
    ])

    if keep_original:
        return (
            upload_block + "\n"
            "if [ $UPLOAD_RC -eq 0 ]; then\n"
            "  echo 'Transfer complete. Source kept.'\n"
            "else\n"
            "  echo 'ERROR: Transfer failed.'\n"
            "  exit $UPLOAD_RC\n"
            "fi"
        )
    return (
        upload_block + "\n"
        f'if [ $UPLOAD_RC -eq 0 ]; then\n'
        f'  rm -rf {q(src)} && echo "Transfer complete. Source deleted."\n'
        f'else\n'
        f'  echo "ERROR: Transfer failed. Source was NOT deleted."\n'
        f'  exit $UPLOAD_RC\n'
        f'fi'
    )


def run_commands(commands: list[list[str]]) -> int:
    """Run a sequence of command lists, stopping at the first non-zero exit code."""
    for command in commands:
        exit_code = run_command(command)
        if exit_code != 0:
            return exit_code
    return 0


def run_command(
    command: Sequence[str],
    stderr: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Run a local command list and return its exit code."""
    err = stderr if stderr is not None else sys.stderr
    executable = command[0] if command else "command"

    try:
        completed = subprocess.run(command, shell=False, check=False, stdout=stdout)
    except FileNotFoundError:
        print(f"Error: '{executable}' was not found in PATH.", file=err)
        return 127

    return completed.returncode
