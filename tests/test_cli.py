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

    def test_version_returns_zero(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main(["version"]), 0)

        self.assertEqual(stdout.getvalue(), "mjolnirtools 1.0.1\n")

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
            "Use one of: mt system resources, mt system nodes, "
            "mt system partitions, mt system node <name>, "
            "mt system partition <name>",
            stderr.getvalue(),
        )

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

    def test_no_args_shows_help(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(cli.main([]), 0)

        help_text = stdout.getvalue()
        self.assertIn("Usage:", help_text)
        self.assertIn("Interactive sessions", help_text)
        self.assertIn("Information", help_text)


if __name__ == "__main__":
    unittest.main()
