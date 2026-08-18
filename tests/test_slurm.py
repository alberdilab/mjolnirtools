import unittest
from unittest import mock

from mjolnirtools import slurm


class SlurmCommandTests(unittest.TestCase):
    def test_interactive_command_uses_defaults(self):
        self.assertEqual(
            slurm.build_interactive_command(hours=4),
            [
                "srun",
                "--nodes=1",
                "--ntasks=1",
                "--cpus-per-task=4",
                "--mem=8G",
                "--time=4:00:00",
                "--pty",
                "bash",
            ],
        )

    def test_interactive_command_uses_custom_resources(self):
        self.assertEqual(
            slurm.build_interactive_command(hours=4, cpus=8, mem="16G"),
            [
                "srun",
                "--nodes=1",
                "--ntasks=1",
                "--cpus-per-task=8",
                "--mem=16G",
                "--time=4:00:00",
                "--pty",
                "bash",
            ],
        )

    def test_slurm_list_command_uses_current_username(self):
        with mock.patch("getpass.getuser", return_value="alice"):
            self.assertEqual(
                slurm.build_slurm_list_command(),
                [
                    "squeue",
                    "-u",
                    "alice",
                    "--noheader",
                    "--format=%i|%P|%j|%u|%T|%M|%l|%m|%k",
                ],
            )

    def test_slurm_all_command_omits_user_filtering(self):
        self.assertEqual(
            slurm.build_slurm_list_command(all_users=True),
            [
                "squeue",
                "--noheader",
                "--format=%i|%P|%j|%u|%T|%M|%l|%m|%k",
            ],
        )

    def test_slurm_pending_command_filters_current_user_pending_jobs(self):
        with mock.patch("getpass.getuser", return_value="alice"):
            self.assertEqual(
                slurm.build_slurm_pending_command(),
                [
                    "squeue",
                    "-u",
                    "alice",
                    "--states=PENDING",
                    "--noheader",
                    "--format=%i|%P|%j|%u|%T|%M|%l|%m|%k",
                ],
            )

    def test_slurm_running_command_filters_current_user_running_jobs(self):
        with mock.patch("getpass.getuser", return_value="alice"):
            self.assertEqual(
                slurm.build_slurm_running_command(),
                [
                    "squeue",
                    "-u",
                    "alice",
                    "--states=RUNNING",
                    "--noheader",
                    "--format=%i|%P|%j|%u|%T|%M|%l|%m|%k",
                ],
            )

    def test_slurm_job_command_uses_sacct(self):
        self.assertEqual(
            slurm.build_slurm_job_command("12345"),
            [
                "sacct",
                "--parsable2",
                "--noheader",
                "--format=JobID,NCPUS,Elapsed,CPUTime,ReqMem,MaxRSS",
                "--units=G",
                "-j",
                "12345",
            ],
        )

    def test_cancel_command_uses_scancel_with_job_ids(self):
        self.assertEqual(
            slurm.build_slurm_cancel_command(["12345", "12346"]),
            ["scancel", "12345", "12346"],
        )

    def test_cancel_command_accepts_array_and_step_ids(self):
        self.assertEqual(
            slurm.build_slurm_cancel_command(["12345_3", "12346_[1-5]", "12347.batch"]),
            ["scancel", "12345_3", "12346_[1-5]", "12347.batch"],
        )

    def test_cancel_command_drops_duplicate_job_ids(self):
        self.assertEqual(
            slurm.build_slurm_cancel_command(["12345", " 12345 ", "12346"]),
            ["scancel", "12345", "12346"],
        )

    def test_cancel_command_adds_the_requested_signal(self):
        self.assertEqual(
            slurm.build_slurm_cancel_command(["12345"], signal="term"),
            ["scancel", "--signal=TERM", "12345"],
        )

    def test_cancel_command_rejects_an_empty_job_id_list(self):
        with self.assertRaises(ValueError):
            slurm.build_slurm_cancel_command([])

    def test_cancel_command_rejects_a_bare_string(self):
        with self.assertRaises(ValueError):
            slurm.build_slurm_cancel_command("12345")

    def test_cancel_command_rejects_invalid_job_ids(self):
        for job_id in ["", "  ", "all", "12345; rm -rf /", "-u"]:
            with self.subTest(job_id=job_id):
                with self.assertRaises(ValueError):
                    slurm.build_slurm_cancel_command([job_id])

    def test_cancel_command_rejects_an_invalid_signal(self):
        with self.assertRaises(ValueError):
            slurm.build_slurm_cancel_command(["12345"], signal="TERM; ls")

    def test_cancellable_job_ids_are_recognised(self):
        self.assertTrue(slurm.is_cancellable_job_id("12345"))
        self.assertTrue(slurm.is_cancellable_job_id("12345_3"))
        self.assertTrue(slurm.is_cancellable_job_id("12345_[1-5]"))
        self.assertFalse(slurm.is_cancellable_job_id("assembly"))
        self.assertFalse(slurm.is_cancellable_job_id("prokka*"))

    def test_info_nodes_command_uses_sinfo_node_format(self):
        self.assertEqual(
            slurm.build_info_nodes_command(),
            [
                "sinfo",
                "-N",
                "-o",
                "%.20N %.10t %.6c %.10m %.20G",
            ],
        )

    def test_info_partitions_command_uses_sinfo_partition_format(self):
        self.assertEqual(
            slurm.build_info_partitions_command(),
            [
                "sinfo",
                "-o",
                "%P %a %l %D %N",
            ],
        )

    def test_system_node_status_command_uses_scontrol(self):
        self.assertEqual(
            slurm.build_system_node_status_command("node001"),
            [
                "scontrol",
                "show",
                "node",
                "node001",
            ],
        )

    def test_system_partition_status_command_uses_scontrol(self):
        self.assertEqual(
            slurm.build_system_partition_status_command("short"),
            [
                "scontrol",
                "show",
                "partition",
                "short",
            ],
        )

    def test_system_resources_command_uses_scontrol_nodes(self):
        self.assertEqual(
            slurm.build_system_resources_command(),
            [
                "scontrol",
                "show",
                "nodes",
            ],
        )

    def test_empty_node_name_is_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_system_node_status_command("")

    def test_empty_partition_name_is_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_system_partition_status_command("")

    def test_invalid_hours_are_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_interactive_command(hours=0)

    def test_invalid_cpus_are_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_interactive_command(hours=4, cpus=0)

    def test_interactive_command_accepts_partition_and_gpus(self):
        self.assertEqual(
            slurm.build_interactive_command(
                hours=4, cpus=8, mem="64G", partition="gpuqueue", gpus=2
            ),
            [
                "srun",
                "--nodes=1",
                "--ntasks=1",
                "--partition=gpuqueue",
                "--cpus-per-task=8",
                "--gres=gpu:2",
                "--mem=64G",
                "--time=4:00:00",
                "--pty",
                "bash",
            ],
        )

    def test_interactive_command_accepts_a_specific_node(self):
        self.assertEqual(
            slurm.build_interactive_command(hours=2, node="mjolnircomp01fl"),
            [
                "srun",
                "--nodes=1",
                "--ntasks=1",
                "--nodelist=mjolnircomp01fl",
                "--cpus-per-task=4",
                "--mem=8G",
                "--time=2:00:00",
                "--pty",
                "bash",
            ],
        )

    def test_empty_interactive_partition_is_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_interactive_command(hours=4, partition="  ")

    def test_empty_interactive_node_is_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_interactive_command(hours=4, node="")

    def test_invalid_gpus_are_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_interactive_command(hours=4, gpus=0)


if __name__ == "__main__":
    unittest.main()
