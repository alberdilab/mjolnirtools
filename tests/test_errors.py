import errno
import os
import tempfile
import unittest
import urllib.error
from io import StringIO
from pathlib import Path

from rich.console import Console

from mjolnirtools import errors


def _os_error(code: int, path: str) -> OSError:
    return OSError(code, os.strerror(code), path)


class DescribeOsErrorTests(unittest.TestCase):
    def test_permission_denied_is_actionable(self):
        error = errors.describe_os_error(
            _os_error(errno.EACCES, "/maps/projects/demo/run"),
            path="/maps/projects/demo/run",
            action="create",
        )

        self.assertIn("Permission denied", error.message)
        self.assertIn("/maps/projects/demo/run", error.message)
        self.assertTrue(any("write to" in hint for hint in error.hints))

    def test_read_only_filesystem(self):
        error = errors.describe_os_error(_os_error(errno.EROFS, "/mnt/ro/out"), path="/mnt/ro/out")

        self.assertIn("read-only", error.message)

    def test_out_of_space(self):
        error = errors.describe_os_error(_os_error(errno.ENOSPC, "/scratch/out"), path="/scratch/out")

        self.assertIn("no space left", error.message)
        self.assertTrue(any("mt list big" in hint for hint in error.hints))

    def test_quota_exhausted(self):
        code = getattr(errno, "EDQUOT", None)
        if code is None:
            self.skipTest("EDQUOT is not defined on this platform")
        error = errors.describe_os_error(_os_error(code, "/home/user/out"), path="/home/user/out")

        self.assertIn("quota", error.message)

    def test_missing_parent_directory(self):
        error = errors.describe_os_error(_os_error(errno.ENOENT, "/nope/out"), path="/nope/out")

        self.assertIn("does not exist", error.message)

    def test_parent_is_a_file(self):
        error = errors.describe_os_error(_os_error(errno.ENOTDIR, "/tmp/file.txt/out"))

        self.assertIn("not a directory", error.message)

    def test_unavailable_mount(self):
        error = errors.describe_os_error(_os_error(errno.ESTALE, "/maps/projects/demo"))

        self.assertIn("not responding", error.message)

    def test_unknown_errno_falls_back_to_strerror(self):
        error = errors.describe_os_error(_os_error(errno.EAGAIN, "/tmp/out"), path="/tmp/out")

        self.assertIn("/tmp/out", error.message)
        self.assertNotIn("Traceback", error.message)

    def test_url_error_is_reported_as_network_failure(self):
        error = errors.describe_os_error(urllib.error.URLError("Name or service not known"))

        self.assertIn("Network request failed", error.message)

    def test_http_error_reports_status(self):
        exc = urllib.error.HTTPError("https://example.org", 401, "Unauthorized", {}, None)
        error = errors.describe_os_error(exc)

        self.assertIn("401", error.message)


class DescribeErrorTests(unittest.TestCase):
    def test_user_error_passes_through(self):
        original = errors.UserError("boom", ["hint"])

        self.assertIs(errors.describe_error(original), original)

    def test_os_error_is_translated(self):
        error = errors.describe_error(_os_error(errno.EACCES, "/tmp/x"), path="/tmp/x")

        self.assertIn("Permission denied", error.message)

    def test_other_exceptions_get_a_short_message(self):
        error = errors.describe_error(ValueError("bad value"))

        self.assertEqual(error.message, "ValueError: bad value")


class ExpandPathTests(unittest.TestCase):
    def test_empty_input_is_rejected(self):
        with self.assertRaises(errors.UserError):
            errors.expand_path("   ")

    def test_user_home_is_expanded(self):
        self.assertEqual(errors.expand_path("~"), Path.home().resolve())


class EnsureWritableDirectoryTests(unittest.TestCase):
    def test_creates_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b"
            errors.ensure_writable_directory(target)

            self.assertTrue(target.is_dir())

    def test_leaves_no_probe_file_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "workspace"
            errors.ensure_writable_directory(target)

            self.assertEqual(list(target.iterdir()), [])

    def test_existing_file_at_path_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "workspace"
            target.write_text("not a directory")

            with self.assertRaises(errors.UserError) as ctx:
                errors.ensure_writable_directory(target)

            self.assertIn("a file already exists", ctx.exception.message)

    def test_unwritable_parent_is_reported_as_permission_error(self):
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions")
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "locked"
            parent.mkdir(mode=0o500)
            try:
                with self.assertRaises(errors.UserError) as ctx:
                    errors.ensure_writable_directory(parent / "workspace")
            finally:
                parent.chmod(0o700)

            self.assertIn("Permission denied", ctx.exception.message)

    def test_existing_directory_without_write_access_is_reported(self):
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "workspace"
            target.mkdir(mode=0o500)
            try:
                with self.assertRaises(errors.UserError) as ctx:
                    errors.ensure_writable_directory(target)
            finally:
                target.chmod(0o700)

            self.assertIn("Permission denied", ctx.exception.message)


class EnsureReadablePathTests(unittest.TestCase):
    def test_missing_path_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(errors.UserError) as ctx:
                errors.ensure_readable_path(Path(tmp) / "missing")

            self.assertIn("Path not found", ctx.exception.message)

    def test_unreadable_directory_is_reported(self):
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data"
            target.mkdir(mode=0o000)
            try:
                with self.assertRaises(errors.UserError) as ctx:
                    errors.ensure_readable_path(target)
            finally:
                target.chmod(0o700)

            self.assertIn("Permission denied", ctx.exception.message)


class PrintUserErrorTests(unittest.TestCase):
    def test_message_and_hints_are_printed(self):
        buffer = StringIO()
        console = Console(file=buffer, width=100, force_terminal=False)
        errors.print_user_error(console, errors.UserError("Nope.", ["Try this."]), indent="  ")
        output = buffer.getvalue()

        self.assertIn("Error: Nope.", output)
        self.assertIn("Try this.", output)


if __name__ == "__main__":
    unittest.main()
