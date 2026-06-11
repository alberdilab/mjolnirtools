import io
from pathlib import Path
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import typer

from mjolnirtools import __version__, cli


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

    def test_slurm_interactive_dispatch_runs_constructed_command(self):
        with mock.patch("mjolnirtools.cli.slurm.run_command", return_value=0) as run_command:
            exit_code = cli.main(
                ["slurm", "interactive", "4", "--cpus", "8", "--mem", "16G"]
            )

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
        self.assertIn("Invalid value for '[HOURS]'", stderr.getvalue())

    def test_invalid_cpus_exit_during_argument_parsing(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["interactive", "4", "--cpus", "0"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Invalid value for '--cpus'", stderr.getvalue())

    def test_slurm_dispatch_lists_current_user_jobs_by_default(self):
        squeue_output = "12345|short|analysis|alice|RUNNING|00:10|1:00:00|8G|\n"

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, squeue_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["slurm"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(cli.slurm.build_slurm_list_command())
        table_output = stdout.getvalue()
        self.assertIn("Slurm Jobs", table_output)
        self.assertIn("12345", table_output)
        self.assertIn("RUNNING", table_output)

    def test_slurm_list_dispatch_lists_current_user_jobs(self):
        squeue_output = "12345|short|analysis|alice|RUNNING|00:10|1:00:00|8G|\n"

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, squeue_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["slurm", "list"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(cli.slurm.build_slurm_list_command())
        self.assertIn("Slurm Jobs", stdout.getvalue())

    def test_slurm_all_dispatch_lists_jobs_without_user_filtering(self):
        squeue_output = "12345|short|analysis|alice|RUNNING|00:10|1:00:00|8G|\n"

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, squeue_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["slurm", "all"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            cli.slurm.build_slurm_list_command(all_users=True)
        )
        self.assertIn("Slurm Jobs", stdout.getvalue())

    def test_slurm_pending_dispatch_lists_pending_jobs(self):
        squeue_output = "12345|short|analysis|alice|PENDING|00:00|1:00:00|8G|\n"

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, squeue_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["slurm", "pending"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            cli.slurm.build_slurm_pending_command()
        )
        table_output = stdout.getvalue()
        self.assertIn("Pending Slurm Jobs", table_output)
        self.assertIn("PENDING", table_output)

    def test_slurm_running_dispatch_lists_running_jobs(self):
        squeue_output = "12345|short|analysis|alice|RUNNING|00:10|1:00:00|8G|\n"

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, squeue_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["slurm", "running"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            cli.slurm.build_slurm_running_command()
        )
        table_output = stdout.getvalue()
        self.assertIn("Running Slurm Jobs", table_output)
        self.assertIn("RUNNING", table_output)

    def test_slurm_job_dispatch_uses_sacct(self):
        sacct_output = "12345|4|00:10:00|00:40:00|8Gc|0.50G\n"

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, sacct_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["slurm", "12345"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "sacct",
                "--parsable2",
                "--noheader",
                "--format=JobID,NCPUS,Elapsed,CPUTime,ReqMem,MaxRSS",
                "--units=G",
                "-j",
                "12345",
            ]
        )
        table_output = stdout.getvalue()
        self.assertIn("Slurm Job 12345", table_output)
        self.assertIn("00:10:00", table_output)

    def test_slurm_rejects_unsupported_target_without_traceback(self):
        stderr = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output"
        ) as capture_command_output:
            with redirect_stderr(stderr):
                exit_code = cli.main(["slurm", "queues"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Usage: mt slurm", stderr.getvalue())
        self.assertIn("mt slurm <jobid>", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())
        capture_command_output.assert_not_called()

    def test_version_returns_zero(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["version"]), 0)

        self.assertEqual(stdout.getvalue(), f"mjolnirtools {__version__}\n")

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

    def test_list_rejects_unsupported_sort_without_traceback(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "owner"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Usage: mt list", stderr.getvalue())
        self.assertIn("Sort must be one of: name, time, size", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_list_with_path_passes_path_to_command(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_filtered", return_value=0) as run_filtered:
            exit_code = cli.main(["list", "name", "/data"])

        self.assertEqual(exit_code, 0)
        run_filtered.assert_called_once_with(
            ["ls", "-lah", "/data"], head=None, dirs_only=False, files_only=False
        )

    def test_list_time_with_path(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_filtered", return_value=0) as run_filtered:
            exit_code = cli.main(["list", "time", "/data"])

        self.assertEqual(exit_code, 0)
        run_filtered.assert_called_once_with(
            ["ls", "-laht", "/data"], head=None, dirs_only=False, files_only=False
        )

    def test_list_head_limits_results(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_filtered", return_value=0) as run_filtered:
            exit_code = cli.main(["list", "--head", "5"])

        self.assertEqual(exit_code, 0)
        run_filtered.assert_called_once_with(
            ["ls", "-lah"], head=5, dirs_only=False, files_only=False
        )

    def test_list_dirs_filters_to_directories(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_filtered", return_value=0) as run_filtered:
            exit_code = cli.main(["list", "--dirs"])

        self.assertEqual(exit_code, 0)
        run_filtered.assert_called_once_with(
            ["ls", "-lah"], head=None, dirs_only=True, files_only=False
        )

    def test_list_files_filters_to_regular_files(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_filtered", return_value=0) as run_filtered:
            exit_code = cli.main(["list", "--files"])

        self.assertEqual(exit_code, 0)
        run_filtered.assert_called_once_with(
            ["ls", "-lah"], head=None, dirs_only=False, files_only=True
        )

    def test_list_rejects_dirs_and_files_together(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "--dirs", "--files"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Use only one of --dirs or --files", stderr.getvalue())

    def test_list_match_expands_glob_pattern(self):
        with mock.patch("mjolnirtools.cli.shell._glob.glob", return_value=["a.fastq.gz"]):
            with mock.patch("mjolnirtools.cli.shell.run_list_filtered", return_value=0) as run_filtered:
                exit_code = cli.main(["list", "--match", "*.fastq.gz"])

        self.assertEqual(exit_code, 0)
        run_filtered.assert_called_once_with(
            ["ls", "-lah", "a.fastq.gz"], head=None, dirs_only=False, files_only=False
        )

    def test_list_days_outside_old_mode_is_rejected(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "--days", "60"])

        self.assertEqual(exit_code, 2)
        self.assertIn("--days is only valid with 'old' mode", stderr.getvalue())

    def test_list_old_uses_find_with_default_days(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list", "old"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(
            ["find", ".", "-type", "f", "-mtime", "+30"]
        )

    def test_list_old_accepts_custom_days(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list", "old", "--days", "60"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(
            ["find", ".", "-type", "f", "-mtime", "+60"]
        )

    def test_list_old_accepts_path(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["list", "old", "/scratch/project"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(
            ["find", "/scratch/project", "-type", "f", "-mtime", "+30"]
        )

    def test_list_old_rejects_sort_order_flags(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "old", "--asc"])

        self.assertEqual(exit_code, 2)
        self.assertIn("'old' mode does not support --asc or --des", stderr.getvalue())

    def test_list_old_rejects_dirs_flag(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "old", "--dirs"])

        self.assertEqual(exit_code, 2)
        self.assertIn("'old' mode does not support --dirs or --files", stderr.getvalue())

    def test_list_big_calls_run_list_big(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_big", return_value=0) as run_big:
            exit_code = cli.main(["list", "big"])

        self.assertEqual(exit_code, 0)
        run_big.assert_called_once_with(path=".", head=None)

    def test_list_big_accepts_path(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_big", return_value=0) as run_big:
            exit_code = cli.main(["list", "big", "/scratch/project"])

        self.assertEqual(exit_code, 0)
        run_big.assert_called_once_with(path="/scratch/project", head=None)

    def test_list_big_accepts_head(self):
        with mock.patch("mjolnirtools.cli.shell.run_list_big", return_value=0) as run_big:
            exit_code = cli.main(["list", "big", "--head", "10"])

        self.assertEqual(exit_code, 0)
        run_big.assert_called_once_with(path=".", head=10)

    def test_list_big_rejects_dirs_flag(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "big", "--dirs"])

        self.assertEqual(exit_code, 2)
        self.assertIn("'big' mode does not support --dirs or --files", stderr.getvalue())

    def test_list_big_rejects_days_option(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["list", "big", "--days", "30"])

        self.assertEqual(exit_code, 2)
        self.assertIn("'big' mode does not support --days", stderr.getvalue())

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

    def test_system_resources_prints_usage_progress_rows(self):
        scontrol_output = (
            "NodeName=node001 Arch=x86_64 CoresPerSocket=32\n"
            "   CPUAlloc=8 CPUEfctv=64 CPUTot=64 CPULoad=3.50\n"
            "   RealMemory=524288 AllocMem=131072 FreeMem=390000\n"
            "   Gres=gpu:a100:4 GresUsed=gpu:a100:1(IDX:0)\n"
            "NodeName=node002 Arch=x86_64 CoresPerSocket=16\n"
            "   CPUAlloc=24 CPUEfctv=32 CPUTot=32 CPULoad=10.20\n"
            "   RealMemory=262144 AllocMem=65536 FreeMem=190000\n"
            "   CfgTRES=cpu=32,mem=262144M,billing=32,gres/gpu=2\n"
            "   AllocTRES=cpu=24,mem=65536M,gres/gpu=2\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, scontrol_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["system", "resources"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "scontrol",
                "show",
                "nodes",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("System Resources", table_output)
        self.assertIn("CPUs", table_output)
        self.assertIn("33.3%", table_output)
        self.assertIn("32 / 96", table_output)
        self.assertIn("GPUs", table_output)
        self.assertIn("50.0%", table_output)
        self.assertIn("3 / 6", table_output)
        self.assertIn("Memory", table_output)
        self.assertIn("25.0%", table_output)
        self.assertIn("192 / 768 GB", table_output)

    def test_system_without_topic_prints_overview_and_relevant_commands(self):
        scontrol_output = (
            "NodeName=node001 Arch=x86_64 CoresPerSocket=32\n"
            "   CPUAlloc=8 CPUEfctv=64 CPUTot=64 CPULoad=3.50\n"
            "   RealMemory=524288 AllocMem=131072 FreeMem=390000\n"
            "   Gres=gpu:a100:4 GresUsed=gpu:a100:1(IDX:0)\n"
            "NodeName=node002 Arch=x86_64 CoresPerSocket=16\n"
            "   CPUAlloc=24 CPUEfctv=32 CPUTot=32 CPULoad=10.20\n"
            "   RealMemory=262144 AllocMem=65536 FreeMem=190000\n"
            "   CfgTRES=cpu=32,mem=262144M,billing=32,gres/gpu=2\n"
            "   AllocTRES=cpu=24,mem=65536M,gres/gpu=2\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, scontrol_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["system"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "scontrol",
                "show",
                "nodes",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("System Overview", table_output)
        self.assertIn("Available", table_output)
        self.assertIn("64", table_output)
        self.assertIn("576 GB", table_output)
        self.assertIn("Relevant System Commands", table_output)
        self.assertIn("mt system resources", table_output)
        self.assertIn("mt system nodes", table_output)
        self.assertIn("mt system partitions", table_output)
        self.assertIn("mt node <name>", table_output)
        self.assertIn("mt partition <name>", table_output)

    def test_system_resources_rejects_name(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["system", "resources", "node001"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt system resources does not accept a name", stderr.getvalue())

    def test_info_nodes_prints_rich_table_with_unique_nodes(self):
        sinfo_output = (
            "NODELIST STATE CPUS MEMORY GRES\n"
            "node001 idle 64 515000 gpu:a100:4\n"
            "node001 alloc 64 515000 gpu:a100:4\n"
            "node002 mixed 32 257000 (null)\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, sinfo_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["system", "nodes"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "sinfo",
                "-N",
                "-o",
                "%.20N %.10t %.6c %.10m %.20G",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("Slurm Nodes", table_output)
        self.assertIn("Node", table_output)
        self.assertIn("node001", table_output)
        self.assertIn("node002", table_output)
        self.assertEqual(table_output.count("node001"), 1)

    def test_info_partitions_prints_rich_table_with_unique_partitions(self):
        sinfo_output = (
            "PARTITION AVAIL TIMELIMIT NODES NODELIST\n"
            "short* up 12:00:00 4 node[001-004]\n"
            "short* up 12:00:00 2 node[005-006]\n"
            "long up 7-00:00:00 8 node[007-014]\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, sinfo_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["system", "partitions"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "sinfo",
                "-o",
                "%P %a %l %D %N",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("Slurm Partitions", table_output)
        self.assertIn("Partition", table_output)
        self.assertIn("short*", table_output)
        self.assertIn("long", table_output)
        self.assertEqual(table_output.count("short*"), 1)

    def test_system_node_prints_detailed_status_table(self):
        scontrol_output = (
            "NodeName=node001 Arch=x86_64 CoresPerSocket=32\n"
            "   CPUAlloc=8 CPUEfctv=64 CPUTot=64 CPULoad=3.50\n"
            "   State=MIXED ThreadsPerCore=1 RealMemory=515000\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, scontrol_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["system", "node", "node001"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "scontrol",
                "show",
                "node",
                "node001",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("Slurm Node node001", table_output)
        self.assertIn("NodeName", table_output)
        self.assertIn("node001", table_output)
        self.assertIn("State", table_output)
        self.assertIn("MIXED", table_output)

    def test_node_shortcut_dispatches_system_node(self):
        scontrol_output = (
            "NodeName=mjolnircomp01fl Arch=x86_64 CoresPerSocket=32\n"
            "   State=IDLE ThreadsPerCore=1 RealMemory=515000\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, scontrol_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["node", "mjolnircomp01fl"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "scontrol",
                "show",
                "node",
                "mjolnircomp01fl",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("Slurm Node mjolnircomp01fl", table_output)
        self.assertIn("NodeName", table_output)

    def test_partition_shortcut_dispatches_system_partition(self):
        scontrol_output = (
            "PartitionName=short AllowGroups=ALL AllowAccounts=ALL\n"
            "   State=UP TotalNodes=4 TotalCPUs=256 MaxTime=12:00:00\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, scontrol_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["partition", "short"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "scontrol",
                "show",
                "partition",
                "short",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("Slurm Partition short", table_output)
        self.assertIn("PartitionName", table_output)

    def test_system_partition_prints_detailed_status_table(self):
        scontrol_output = (
            "PartitionName=short AllowGroups=ALL AllowAccounts=ALL\n"
            "   State=UP TotalNodes=4 TotalCPUs=256 MaxTime=12:00:00\n"
            "   Nodes=node[001-004]\n"
        )

        stdout = io.StringIO()
        with mock.patch(
            "mjolnirtools.cli.slurm.capture_command_output",
            return_value=(0, scontrol_output),
        ) as capture_command_output:
            with redirect_stdout(stdout):
                exit_code = cli.main(["system", "partition", "short"])

        self.assertEqual(exit_code, 0)
        capture_command_output.assert_called_once_with(
            [
                "scontrol",
                "show",
                "partition",
                "short",
            ]
        )

        table_output = stdout.getvalue()
        self.assertIn("Slurm Partition short", table_output)
        self.assertIn("PartitionName", table_output)
        self.assertIn("short", table_output)
        self.assertIn("TotalNodes", table_output)
        self.assertIn("4", table_output)

    def test_system_node_requires_node_name(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["system", "node"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt system node requires a node name", stderr.getvalue())

    def test_system_partition_requires_partition_name(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["system", "partition"])

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "mt system partition requires a partition name", stderr.getvalue()
        )

    def test_system_nodes_rejects_name(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["system", "nodes", "node001"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt system nodes does not accept a node name", stderr.getvalue())

    def test_info_rejects_unknown_topic(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["system", "queues"])

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "Use one of: mt system, mt system resources, mt system nodes, "
            "mt system partitions, mt system node <name>, "
            "mt system partition <name>",
            stderr.getvalue(),
        )

    def test_help_groups_commands_by_topic(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["help"]), 0)

        help_text = stdout.getvalue()
        self.assertNotIn("--help", help_text)
        self.assertIn("File listing", help_text)
        self.assertIn("Job monitoring", help_text)
        self.assertIn("Screen sessions", help_text)
        self.assertIn("Conda environments", help_text)
        self.assertIn("System", help_text)
        self.assertIn("Information", help_text)
        self.assertLess(help_text.index("System"), help_text.index("Information"))
        self.assertEqual(help_text.count("mt system resources"), 1)

    def test_unknown_command_reports_click_error_without_traceback(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["queues"])

        self.assertEqual(exit_code, 2)
        self.assertIn("No such command 'queues'", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_main_help_shows_subcommand_tree(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["help"]), 0)
            self.assertEqual(cli.main([]), 0)

        help_text = stdout.getvalue()
        self.assertNotIn("Command tree:", help_text)
        self.assertNotIn("Subcommands:", help_text)
        self.assertIn("mt slurm pending", help_text)
        self.assertIn("mt screen kill <screenid>", help_text)
        self.assertIn("mt conda create <name>", help_text)
        self.assertIn("mt system resources", help_text)
        self.assertIn("Shortcuts:", help_text)

    def test_topic_help_shows_its_own_subcommands(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["slurm", "--help"]), 0)
            self.assertEqual(cli.main(["screen", "--help"]), 0)
            self.assertEqual(cli.main(["conda", "--help"]), 0)
            self.assertEqual(cli.main(["system", "--help"]), 0)
            self.assertEqual(cli.main(["list", "--help"]), 0)

        help_text = stdout.getvalue()
        self.assertIn("Usage: mt slurm", help_text)
        self.assertIn("Subcommands:", help_text)
        self.assertIn("mt slurm interactive <hours>", help_text)
        self.assertIn("mt slurm list", help_text)
        self.assertIn("mt slurm pending", help_text)
        self.assertIn("mt screen kill <screenid>", help_text)
        self.assertIn("mt conda create <name>", help_text)
        self.assertIn("mt system resources", help_text)
        self.assertIn("mt system partition <name>", help_text)
        self.assertIn("Usage: mt list", help_text)

    def test_help_displays_shortcuts_without_registering_them_as_commands(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["help"]), 0)

        help_text = stdout.getvalue()
        self.assertIn("Shortcuts:", help_text)
        self.assertIn("mt interactive <hours>", help_text)
        self.assertIn("mt node <name>", help_text)
        self.assertIn("mt partition <name>", help_text)

        command = typer.main.get_command(cli.app)
        self.assertNotIn("interactive", command.commands)
        self.assertNotIn("node", command.commands)
        self.assertNotIn("partition", command.commands)
        self.assertIn("system", command.commands)

    def test_mjolnirtools_console_script_is_registered(self):
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

        self.assertIn(
            'mjolnirtools = "mjolnirtools.cli:main"',
            pyproject_path.read_text(),
        )

    def test_mjolnirtools_prog_name_is_supported(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["help"], prog_name="mjolnirtools"), 0)

        self.assertIn("Job monitoring", stdout.getvalue())

    def test_main_help_option_is_not_registered_but_topic_help_is(self):
        command = typer.main.get_command(cli.app)
        self.assertFalse(command.add_help_option)

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["--help"])

        self.assertEqual(exit_code, 2)
        self.assertIn("No such option: --help", stderr.getvalue())

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = cli.main(["slurm", "--help"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Usage: mt slurm", stdout.getvalue())

    def test_mjolnirtools_help_command_uses_prog_name(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["help"], prog_name="mjolnirtools"), 0)

        self.assertIn("mt node <name> = mt system node <name>", stdout.getvalue())

    def test_no_args_shows_help(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main([]), 0)

        help_text = stdout.getvalue()
        self.assertIn("Shortcuts:", help_text)
        self.assertIn("Job monitoring", help_text)
        self.assertIn("Information", help_text)


    def test_permissions_exec_non_recursive_makes_path_executable(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "exec", "script.sh", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "+x", "script.sh"])

    def test_permissions_exec_recursive_uses_find(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "exec", "scripts/"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(
            ["find", "scripts/", "-exec", "chmod", "+x", "{}", "+"]
        )

    def test_permissions_exec_defaults_to_current_directory(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "exec"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["find", ".", "-exec", "chmod", "+x", "{}", "+"])

    def test_permissions_open_non_recursive_on_directory_uses_755(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "open", ".", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "755", "."])

    def test_permissions_open_non_recursive_on_file_uses_644(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            with mock.patch("pathlib.Path.is_dir", return_value=False):
                exit_code = cli.main(["permissions", "open", "data.csv", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "644", "data.csv"])

    def test_permissions_open_recursive_applies_755_to_dirs_and_644_to_files(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "open", "project/"])

        self.assertEqual(exit_code, 0)
        run_command.assert_has_calls([
            mock.call(["find", "project/", "-type", "d", "-exec", "chmod", "755", "{}", "+"]),
            mock.call(["find", "project/", "-type", "f", "-exec", "chmod", "644", "{}", "+"]),
        ])

    def test_permissions_private_non_recursive_on_directory_uses_700(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "private", ".", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "700", "."])

    def test_permissions_private_non_recursive_on_file_uses_600(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            with mock.patch("pathlib.Path.is_dir", return_value=False):
                exit_code = cli.main(["permissions", "private", "secret.txt", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "600", "secret.txt"])

    def test_permissions_private_recursive_applies_700_to_dirs_and_600_to_files(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "private", "project/"])

        self.assertEqual(exit_code, 0)
        run_command.assert_has_calls([
            mock.call(["find", "project/", "-type", "d", "-exec", "chmod", "700", "{}", "+"]),
            mock.call(["find", "project/", "-type", "f", "-exec", "chmod", "600", "{}", "+"]),
        ])

    def test_permissions_shared_non_recursive_on_directory_applies_775_and_setgid(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "shared", ".", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_has_calls([
            mock.call(["chmod", "775", "."]),
            mock.call(["chmod", "g+s", "."]),
        ])

    def test_permissions_shared_non_recursive_on_file_uses_664(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            with mock.patch("pathlib.Path.is_dir", return_value=False):
                exit_code = cli.main(["permissions", "shared", "results.csv", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "664", "results.csv"])

    def test_permissions_shared_recursive_applies_775_and_setgid_to_dirs_and_664_to_files(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "shared", "project/"])

        self.assertEqual(exit_code, 0)
        run_command.assert_has_calls([
            mock.call(["find", "project/", "-type", "d", "-exec", "chmod", "775", "{}", "+"]),
            mock.call(["find", "project/", "-type", "d", "-exec", "chmod", "g+s", "{}", "+"]),
            mock.call(["find", "project/", "-type", "f", "-exec", "chmod", "664", "{}", "+"]),
        ])

    def test_permissions_fix_non_recursive_on_directory_uses_755(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "fix", ".", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "755", "."])

    def test_permissions_fix_non_recursive_on_file_uses_644(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            with mock.patch("pathlib.Path.is_dir", return_value=False):
                exit_code = cli.main(["permissions", "fix", "output.txt", "--non-recursive"])

        self.assertEqual(exit_code, 0)
        run_command.assert_called_once_with(["chmod", "644", "output.txt"])

    def test_permissions_fix_recursive_applies_755_to_dirs_and_644_to_files(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
            exit_code = cli.main(["permissions", "fix", "project/"])

        self.assertEqual(exit_code, 0)
        run_command.assert_has_calls([
            mock.call(["find", "project/", "-type", "d", "-exec", "chmod", "755", "{}", "+"]),
            mock.call(["find", "project/", "-type", "f", "-exec", "chmod", "644", "{}", "+"]),
        ])

    def test_permissions_stops_on_first_command_failure(self):
        with mock.patch("mjolnirtools.cli.shell.run_command", return_value=1) as run_command:
            exit_code = cli.main(["permissions", "shared", "project/"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(run_command.call_count, 1)

    def test_permissions_rejects_unknown_action(self):
        stderr = io.StringIO()
        with mock.patch("mjolnirtools.cli.shell.run_command"):
            with redirect_stderr(stderr):
                exit_code = cli.main(["permissions", "public"])

        self.assertEqual(exit_code, 2)
        self.assertIn(
            "Use one of: mt permissions exec, open, private, shared, fix",
            stderr.getvalue(),
        )

    def test_move_erda_dispatches_screen_command_when_erda_is_configured(self):
        with mock.patch("mjolnirtools.cli.config_module._config_has_erda", return_value=True):
            with mock.patch("mjolnirtools.cli.shell.is_inside_screen", return_value=False):
                with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
                    exit_code = cli.main(
                        ["move", "erda", "/local/data/project", "/erda/projects/myproject"]
                    )

        self.assertEqual(exit_code, 0)
        args = run_command.call_args[0][0]
        self.assertEqual(args[0], "screen")
        self.assertIn("-dmS", args)
        script = args[-1]
        self.assertIn("rsync", script)
        self.assertIn("erda:/erda/projects/myproject", script)

    def test_move_erda_runs_inline_when_inside_screen(self):
        with mock.patch("mjolnirtools.cli.config_module._config_has_erda", return_value=True):
            with mock.patch("mjolnirtools.cli.shell.is_inside_screen", return_value=True):
                with mock.patch("mjolnirtools.cli.shell.run_command", return_value=0) as run_command:
                    exit_code = cli.main(
                        ["move", "erda", "/local/data/project", "/erda/projects/myproject"]
                    )

        self.assertEqual(exit_code, 0)
        args = run_command.call_args[0][0]
        self.assertEqual(args[:2], ["bash", "-c"])

    def test_move_erda_rejects_missing_erda_dest(self):
        stderr = io.StringIO()
        with mock.patch("mjolnirtools.cli.config_module._config_has_erda", return_value=True):
            with redirect_stderr(stderr):
                exit_code = cli.main(["move", "erda", "/local/data/project"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt move erda requires a destination path on ERDA", stderr.getvalue())

    def test_move_erda_rejects_unconfigured_erda(self):
        stderr = io.StringIO()
        with mock.patch("mjolnirtools.cli.config_module._config_has_erda", return_value=False):
            with redirect_stderr(stderr):
                exit_code = cli.main(
                    ["move", "erda", "/local/data/project", "/erda/projects/myproject"]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("ERDA is not configured", stderr.getvalue())

    def test_move_rejects_unknown_destination(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = cli.main(["move", "cloud", "/local/data"])

        self.assertEqual(exit_code, 2)
        self.assertIn("mt move scratch", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
