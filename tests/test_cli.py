import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from mjolnirtools import cli


class CliTests(unittest.TestCase):
    def test_interactive_dispatch_runs_constructed_command(self):
        with mock.patch("mjolnirtools.cli.slurm.run_command", return_value=0) as run_command:
            exit_code = cli.main(["interactive", "4", "--cpus", "8", "--mem", "16G"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(
            [
                "srun",
                "--nodes=1",
                "--ntasks=1",
                "--cpus-per-task=8",
                "--mem=16G",
                "--time=4:00:00",
                "--pty",
                "bash",
            ]
        )

    def test_invalid_hours_exit_during_argument_parsing(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["interactive", "0"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Invalid value for 'HOURS'", stderr.getvalue())

    def test_invalid_cpus_exit_during_argument_parsing(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["interactive", "4", "--cpus", "0"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Invalid value for '--cpus'", stderr.getvalue())

    def test_slurm_dispatch_lists_current_user_jobs_by_default(self):
        with mock.patch("mjolnirtools.cli.slurm.run_command", return_value=0) as run_command:
            exit_code = cli.main(["slurm"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(cli.slurm.build_slurm_list_command())

    def test_slurm_list_dispatch_lists_current_user_jobs(self):
        with mock.patch("mjolnirtools.cli.slurm.run_command", return_value=0) as run_command:
            exit_code = cli.main(["slurm", "list"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(cli.slurm.build_slurm_list_command())

    def test_slurm_all_dispatch_lists_jobs_without_user_filtering(self):
        with mock.patch("mjolnirtools.cli.slurm.run_command", return_value=0) as run_command:
            exit_code = cli.main(["slurm", "all"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(cli.slurm.build_slurm_list_command(all_users=True))

    def test_slurm_job_dispatch_uses_sacct(self):
        with mock.patch("mjolnirtools.cli.slurm.run_command", return_value=0) as run_command:
            exit_code = cli.main(["slurm", "12345"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(
            [
                "sacct",
                "--format=JobID,NCPUS,Elapsed,CPUTime,ReqMem,maxrss",
                "--units=G",
                "-j",
                "12345",
            ]
        )

    def test_version_returns_zero(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["version"]), 0)

        self.assertEqual(stdout.getvalue(), "mjolnirtools 1.0.0\n")

    def test_list_dispatch_runs_default_listing(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["ls", "-lah"])

    def test_list_time_sorts_by_time_descending_by_default(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list", "time"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["ls", "-laht"])

    def test_list_time_can_sort_ascending(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list", "time", "--asc"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["ls", "-lahtr"])

    def test_list_size_sorts_by_size_descending_by_default(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list", "size"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["ls", "-lahS"])

    def test_list_name_can_sort_descending(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list", "--des"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["ls", "-lahr"])

    def test_list_rejects_conflicting_sort_orders(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "time", "--asc", "--des"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Use only one of --asc or --des", stderr.getvalue())

    def test_screen_dispatch_attaches_to_session(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["screen", "12345.session"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["screen", "-r", "12345.session"])

    def test_screen_list_dispatch_lists_sessions(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["screen", "list"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["screen", "-ls"])

    def test_screen_kill_dispatch_kills_session(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["screen", "kill", "12345.session"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["screen", "-S", "12345.session", "-X", "quit"])

    def test_screen_kill_requires_session_id(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["screen", "kill"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt screen kill requires a screen id", stderr.getvalue())

    def test_conda_create_dispatch_creates_environment(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["conda", "create", "analysis"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["conda", "create", "--name", "analysis"])

    def test_conda_remove_dispatch_removes_environment(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["conda", "remove", "analysis"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["conda", "env", "remove", "--name", "analysis"])

    def test_conda_list_dispatch_lists_environments(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["conda", "list"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["conda", "env", "list"])

    def test_conda_create_requires_environment_name(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["conda", "create"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt conda create requires an environment name", stderr.getvalue())

    def test_conda_list_rejects_environment_name(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["conda", "list", "analysis"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt conda list does not accept an environment name", stderr.getvalue())

    def test_help_groups_commands_by_topic(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["--help"]), 0)

        help_text = stdout.getvalue()
        self.assertIn("Interactive sessions", help_text)
        self.assertIn("File listing", help_text)
        self.assertIn("Job monitoring", help_text)
        self.assertIn("Screen sessions", help_text)
        self.assertIn("Conda environments", help_text)
        self.assertIn("Information", help_text)


if __name__ == "__main__":
    unittest.main()
