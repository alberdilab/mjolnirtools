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
                    "--format=%.18i %.9P %.30j %.8u %.8T %.10M %.9l %.6m %k",
                ],
            )

    def test_slurm_all_command_omits_user_filtering(self):
        self.assertEqual(
            slurm.build_slurm_list_command(all_users=True),
            [
                "squeue",
                "--format=%.18i %.9P %.30j %.8u %.8T %.10M %.9l %.6m %k",
            ],
        )

    def test_slurm_job_command_uses_sacct(self):
        self.assertEqual(
            slurm.build_slurm_job_command("12345"),
            [
                "sacct",
                "--format=JobID,NCPUS,Elapsed,CPUTime,ReqMem,maxrss",
                "--units=G",
                "-j",
                "12345",
            ],
        )

    def test_invalid_hours_are_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_interactive_command(hours=0)

    def test_invalid_cpus_are_rejected(self):
        with self.assertRaises(ValueError):
            slurm.build_interactive_command(hours=4, cpus=0)


if __name__ == "__main__":
    unittest.main()
