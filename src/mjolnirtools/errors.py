"""User-facing translation of OS and filesystem errors.

Commands in mjolnirtools touch shared HPC filesystems, network mounts, and the
user's home directory, so a single wrong path can raise a wide range of
``OSError`` subclasses. This module turns those into one short sentence plus a
few actionable hints, so users never see a Python traceback.
"""

from __future__ import annotations

import errno
import os
import urllib.error
import uuid
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console


class UserError(Exception):
    """An error meant to be shown as a short message with optional hints."""

    def __init__(self, message: str, hints: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.hints = tuple(hints)


# Errors that mean "the storage backend itself is unavailable", which is common
# on the network mounts used for project and scratch space.
_UNAVAILABLE_ERRNOS = {
    getattr(errno, name)
    for name in ("ESTALE", "ENOTCONN", "EHOSTDOWN", "EHOSTUNREACH", "ETIMEDOUT", "EIO", "ENXIO", "EREMOTEIO", "ENODEV")
    if hasattr(errno, name)
}

_QUOTA_ERRNOS = {getattr(errno, name) for name in ("EDQUOT",) if hasattr(errno, name)}


def _format_target(path: Path | str | None) -> str:
    """Return a printable representation of the path an error refers to."""
    if path is None:
        return "the requested path"
    return str(path)


def _first_existing_parent(path: Path) -> Path | None:
    """Return the closest existing ancestor of ``path``, if any."""
    try:
        for candidate in [path, *path.parents]:
            if candidate.exists():
                return candidate
    except OSError:
        return None
    return None


def _permission_hints(path: Path | str | None) -> list[str]:
    """Build hints for a permission failure, naming the blocking directory."""
    hints: list[str] = []
    if path is not None:
        parent = _first_existing_parent(Path(path))
        if parent is not None:
            hints.append(f"Check the owner and permissions:  ls -ld {parent}")
    hints.append("Choose a directory you can write to, such as your home or scratch space.")
    hints.append("Ask the project or data owner to grant you write access if you need this exact location.")
    return hints


def describe_os_error(
    exc: OSError,
    *,
    path: Path | str | None = None,
    action: str = "use",
) -> UserError:
    """Translate an ``OSError`` into a user-facing message with hints."""
    # urllib raises OSError subclasses, so network failures land here too.
    if isinstance(exc, urllib.error.HTTPError):
        return UserError(
            f"The server rejected the request: HTTP {exc.code} {exc.reason}.",
            ["Check your credentials and try again; if it persists, the service may be down."],
        )
    if isinstance(exc, urllib.error.URLError):
        return UserError(
            f"Network request failed: {exc.reason}.",
            [
                "Check that this machine has internet access (compute nodes are often offline).",
                "Retry from a login node, or try again later.",
            ],
        )
    if isinstance(exc, TimeoutError) and exc.errno is None:
        return UserError(
            "The operation timed out.",
            ["Check your network or filesystem mount, then try again."],
        )

    target = _format_target(path if path is not None else getattr(exc, "filename", None))
    code = exc.errno
    detail = exc.strerror or str(exc)

    if code in (errno.EACCES, errno.EPERM):
        return UserError(
            f"Permission denied: you cannot {action} {target}.",
            _permission_hints(path if path is not None else getattr(exc, "filename", None)),
        )
    if code == errno.EROFS:
        return UserError(
            f"Cannot {action} {target}: the filesystem is mounted read-only.",
            ["Pick a location on a writable filesystem, such as your home or scratch space."],
        )
    if code == errno.ENOSPC:
        return UserError(
            f"Cannot {action} {target}: no space left on the filesystem.",
            [
                "Free up space or choose a different filesystem.",
                "Inspect what is using space:  mt list big <path>",
            ],
        )
    if code in _QUOTA_ERRNOS:
        return UserError(
            f"Cannot {action} {target}: your disk quota is exhausted.",
            [
                "Delete or archive files you no longer need, or use a location with free quota.",
                "Inspect what is using space:  mt list big <path>",
            ],
        )
    if code == errno.ENOENT:
        return UserError(
            f"Cannot {action} {target}: part of the path does not exist.",
            [
                "Check the path for typos.",
                "Create the parent directory first, or choose an existing one.",
            ],
        )
    if code == errno.ENOTDIR:
        return UserError(
            f"Cannot {action} {target}: part of the path is a file, not a directory.",
            ["Choose a path whose parent directories are all directories."],
        )
    if code == errno.EEXIST:
        return UserError(
            f"Cannot {action} {target}: something already exists at that path.",
            ["Choose a different name, or remove the existing entry first."],
        )
    if code == errno.EISDIR:
        return UserError(
            f"Cannot {action} {target}: the path is a directory, but a file was expected.",
            ["Pass a file path instead of a directory."],
        )
    if code == errno.ENAMETOOLONG:
        return UserError(
            f"Cannot {action} {target}: the path name is too long.",
            ["Use a shorter directory or file name."],
        )
    if code == errno.ELOOP:
        return UserError(
            f"Cannot {action} {target}: the path contains a symbolic link loop.",
            ["Resolve the symlinks in the path, or use the real location."],
        )
    if code in (errno.EMFILE, errno.ENFILE):
        return UserError(
            f"Cannot {action} {target}: too many files are open.",
            ["Close other running jobs or raise the open-file limit:  ulimit -n"],
        )
    if code in _UNAVAILABLE_ERRNOS:
        return UserError(
            f"Cannot {action} {target}: the filesystem is not responding.",
            [
                "This usually means a network mount is down or temporarily unavailable.",
                "Check that the location is mounted, wait a moment, and try again.",
            ],
        )
    return UserError(f"Cannot {action} {target}: {detail}.")


def describe_error(
    exc: BaseException,
    *,
    path: Path | str | None = None,
    action: str = "use",
) -> UserError:
    """Translate any exception into a user-facing message with hints."""
    if isinstance(exc, UserError):
        return exc
    if isinstance(exc, OSError):
        return describe_os_error(exc, path=path, action=action)
    return UserError(f"{type(exc).__name__}: {exc}")


def print_user_error(
    console: Console,
    error: UserError,
    *,
    indent: str = "",
    show_hints: bool = True,
) -> None:
    """Print a user-facing error and its hints without a traceback."""
    console.print(f"{indent}[bold red]Error:[/bold red] {error.message}")
    if not show_hints:
        return
    for hint in error.hints:
        console.print(f"{indent}  [dim]{hint}[/dim]")


def expand_path(raw: str, *, action: str = "use") -> Path:
    """Expand and resolve a user-supplied path, raising :class:`UserError` on bad input."""
    text = raw.strip()
    if not text:
        raise UserError("No path was given.", ["Enter a path, or accept the suggested default."])
    try:
        return Path(text).expanduser().resolve()
    except OSError as exc:
        raise describe_os_error(exc, path=text, action=action) from exc
    except RuntimeError as exc:  # e.g. '~unknownuser' cannot be expanded
        raise UserError(f"Cannot {action} '{text}': {exc}.") from exc


def ensure_writable_directory(path: Path, *, action: str = "write to") -> Path:
    """Create ``path`` if needed and confirm files can actually be written inside it.

    Permission problems on shared filesystems often only surface on the first
    write (group ACLs, read-only mounts, exhausted quota), so the directory is
    probed with a real file rather than trusting ``os.access``.
    """
    if path.exists() and not path.is_dir():
        raise UserError(
            f"Cannot {action} {path}: a file already exists at that path.",
            ["Choose a different directory name."],
        )

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise describe_os_error(exc, path=path, action="create") from exc

    probe = path / f".mt-write-test-{uuid.uuid4().hex}"
    try:
        probe.touch()
    except OSError as exc:
        raise describe_os_error(exc, path=path, action=action) from exc
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
    return path


def ensure_readable_path(path: Path, *, action: str = "read") -> Path:
    """Confirm ``path`` exists and is readable, raising :class:`UserError` otherwise."""
    try:
        exists = path.exists()
    except OSError as exc:
        raise describe_os_error(exc, path=path, action=action) from exc
    if not exists:
        raise UserError(
            f"Path not found: {path}.",
            ["Check the path for typos, or list the parent directory:  mt list <path>"],
        )
    if not os.access(path, os.R_OK) or (path.is_dir() and not os.access(path, os.X_OK)):
        raise UserError(
            f"Permission denied: you cannot {action} {path}.",
            _permission_hints(path),
        )
    return path
