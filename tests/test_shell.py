import subprocess
import unittest
from unittest import mock

from mjolnirtools import shell


class ShellCommandTests(unittest.TestCase):
    def test_list_command_uses_default_name_sort(self):
        self.assertEqual(shell.build_list_command(), ["ls", "-lah"])

    def test_list_command_sorts_name_descending(self):
        self.assertEqual(shell.build_list_command(order="des"), ["ls", "-lahr"])

    def test_list_command_sorts_time_descending_by_default(self):
        self.assertEqual(shell.build_list_command(sort_by="time"), ["ls", "-laht"])

    def test_list_command_sorts_time_ascending(self):
        self.assertEqual(shell.build_list_command(sort_by="time", order="asc"), ["ls", "-lahtr"])

    def test_list_command_sorts_size_descending_by_default(self):
        self.assertEqual(shell.build_list_command(sort_by="size"), ["ls", "-lahS"])

    def test_list_command_sorts_size_ascending(self):
        self.assertEqual(shell.build_list_command(sort_by="size", order="asc"), ["ls", "-lahSr"])

    def test_list_command_appends_non_default_path(self):
        self.assertEqual(shell.build_list_command(path="/data"), ["ls", "-lah", "/data"])

    def test_list_command_omits_dot_path(self):
        self.assertEqual(shell.build_list_command(path="."), ["ls", "-lah"])

    def test_list_command_match_expands_glob(self):
        with mock.patch("mjolnirtools.shell._glob.glob", return_value=["/d/a.txt", "/d/b.txt"]):
            result = shell.build_list_command(path="/d", match="*.txt")
        self.assertEqual(result, ["ls", "-lah", "/d/a.txt", "/d/b.txt"])

    def test_list_command_match_returns_empty_list_when_no_files(self):
        with mock.patch("mjolnirtools.shell._glob.glob", return_value=[]):
            result = shell.build_list_command(path=".", match="*.bam")
        self.assertEqual(result, [])

    def test_invalid_sort_is_rejected(self):
        with self.assertRaises(ValueError):
            shell.build_list_command(sort_by="date")

    def test_invalid_order_is_rejected(self):
        with self.assertRaises(ValueError):
            shell.build_list_command(order="descending")

    def test_list_old_command_default(self):
        self.assertEqual(
            shell.build_list_old_command(),
            ["find", ".", "-type", "f", "-mtime", "+30"],
        )

    def test_list_old_command_custom_days(self):
        self.assertEqual(
            shell.build_list_old_command(days=60),
            ["find", ".", "-type", "f", "-mtime", "+60"],
        )

    def test_list_old_command_custom_path(self):
        self.assertEqual(
            shell.build_list_old_command(path="/scratch/project", days=14),
            ["find", "/scratch/project", "-type", "f", "-mtime", "+14"],
        )

    def test_list_old_command_rejects_zero_days(self):
        with self.assertRaises(ValueError):
            shell.build_list_old_command(days=0)

    def test_parse_human_size_gigabytes(self):
        self.assertAlmostEqual(shell._parse_human_size("2.0G"), 2.0 * 1024 ** 3)

    def test_parse_human_size_megabytes(self):
        self.assertAlmostEqual(shell._parse_human_size("512M"), 512 * 1024 ** 2)

    def test_parse_human_size_kilobytes(self):
        self.assertAlmostEqual(shell._parse_human_size("4K"), 4 * 1024)

    def test_parse_human_size_plain_bytes(self):
        self.assertAlmostEqual(shell._parse_human_size("1024"), 1024.0)

    def test_parse_human_size_empty_string(self):
        self.assertEqual(shell._parse_human_size(""), 0.0)

    def test_run_list_filtered_delegates_when_no_filters(self):
        with mock.patch("mjolnirtools.shell.run_command", return_value=0) as run_cmd:
            result = shell.run_list_filtered(["ls", "-lah"])
        self.assertEqual(result, 0)
        run_cmd.assert_called_once_with(["ls", "-lah"])

    def test_run_list_filtered_returns_error_for_empty_command(self):
        result = shell.run_list_filtered([])
        self.assertEqual(result, 1)

    def test_run_list_filtered_limits_with_head(self):
        ls_output = "total 0\n-rw-r--r-- 1 u g 0 Jan 1 a\n-rw-r--r-- 1 u g 0 Jan 1 b\n-rw-r--r-- 1 u g 0 Jan 1 c\n"
        completed = mock.Mock(spec=subprocess.CompletedProcess)
        completed.stdout = ls_output
        completed.stderr = ""
        completed.returncode = 0
        with mock.patch("mjolnirtools.shell.subprocess.run", return_value=completed):
            with mock.patch("mjolnirtools.shell.sys.stdout") as mock_stdout:
                result = shell.run_list_filtered(["ls", "-lah"], head=2)
        self.assertEqual(result, 0)
        written = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertIn("total 0", written)
        self.assertIn(" a\n", written)
        self.assertIn(" b\n", written)
        self.assertNotIn(" c\n", written)

    def test_run_list_filtered_dirs_only(self):
        ls_output = "total 0\ndrwxr-xr-x 2 u g 0 Jan 1 subdir\n-rw-r--r-- 1 u g 0 Jan 1 file\n"
        completed = mock.Mock(spec=subprocess.CompletedProcess)
        completed.stdout = ls_output
        completed.stderr = ""
        completed.returncode = 0
        with mock.patch("mjolnirtools.shell.subprocess.run", return_value=completed):
            with mock.patch("mjolnirtools.shell.sys.stdout") as mock_stdout:
                result = shell.run_list_filtered(["ls", "-lah"], dirs_only=True)
        self.assertEqual(result, 0)
        written = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertIn("subdir", written)
        self.assertNotIn("file", written)

    def test_run_list_filtered_files_only(self):
        ls_output = "total 0\ndrwxr-xr-x 2 u g 0 Jan 1 subdir\n-rw-r--r-- 1 u g 0 Jan 1 file\n"
        completed = mock.Mock(spec=subprocess.CompletedProcess)
        completed.stdout = ls_output
        completed.stderr = ""
        completed.returncode = 0
        with mock.patch("mjolnirtools.shell.subprocess.run", return_value=completed):
            with mock.patch("mjolnirtools.shell.sys.stdout") as mock_stdout:
                result = shell.run_list_filtered(["ls", "-lah"], files_only=True)
        self.assertEqual(result, 0)
        written = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
        self.assertIn("file", written)
        self.assertNotIn("subdir", written)

    def test_run_list_big_sorts_by_size_descending(self):
        du_output = "512K\t./small\n2.0G\t./large\n100M\t./medium\n3.0G\t.\n"
        completed = mock.Mock(spec=subprocess.CompletedProcess)
        completed.stdout = du_output
        completed.stderr = ""
        completed.returncode = 0
        printed = []
        with mock.patch("mjolnirtools.shell.subprocess.run", return_value=completed):
            with mock.patch("builtins.print", side_effect=lambda x: printed.append(x)):
                result = shell.run_list_big()
        self.assertEqual(result, 0)
        self.assertIn("large", printed[1])
        self.assertIn("medium", printed[2])
        self.assertIn("small", printed[3])

    def test_run_list_big_respects_head(self):
        du_output = "512K\t./small\n2.0G\t./large\n100M\t./medium\n"
        completed = mock.Mock(spec=subprocess.CompletedProcess)
        completed.stdout = du_output
        completed.stderr = ""
        completed.returncode = 0
        printed = []
        with mock.patch("mjolnirtools.shell.subprocess.run", return_value=completed):
            with mock.patch("builtins.print", side_effect=lambda x: printed.append(x)):
                result = shell.run_list_big(head=2)
        self.assertEqual(result, 0)
        self.assertEqual(len(printed), 2)
        self.assertIn("large", printed[0])

    def test_screen_attach_command_uses_session_id(self):
        self.assertEqual(
            shell.build_screen_attach_command("12345.session"),
            ["screen", "-r", "12345.session"],
        )

    def test_screen_list_command_lists_sessions(self):
        self.assertEqual(shell.build_screen_list_command(), ["screen", "-ls"])

    def test_screen_kill_command_uses_session_id(self):
        self.assertEqual(
            shell.build_screen_kill_command("12345.session"),
            ["screen", "-S", "12345.session", "-X", "quit"],
        )

    def test_blank_screen_id_is_rejected(self):
        with self.assertRaises(ValueError):
            shell.build_screen_attach_command("")

    def test_conda_create_command_uses_environment_name(self):
        self.assertEqual(
            shell.build_conda_create_command("analysis"),
            ["conda", "create", "--name", "analysis"],
        )

    def test_conda_remove_command_uses_environment_name(self):
        self.assertEqual(
            shell.build_conda_remove_command("analysis"),
            ["conda", "env", "remove", "--name", "analysis"],
        )

    def test_conda_list_command_lists_environments(self):
        self.assertEqual(shell.build_conda_list_command(), ["conda", "env", "list"])

    def test_conda_export_command_uses_environment_name(self):
        self.assertEqual(
            shell.build_conda_export_command("analysis"),
            ["conda", "env", "export", "--name", "analysis"],
        )

    def test_conda_export_command_supports_from_history(self):
        self.assertEqual(
            shell.build_conda_export_command("analysis", from_history=True),
            ["conda", "env", "export", "--name", "analysis", "--from-history"],
        )

    def test_blank_conda_environment_name_is_rejected(self):
        with self.assertRaises(ValueError):
            shell.build_conda_create_command("")

    def test_build_move_erda_script_keep_original(self):
        script = shell.build_move_erda_script(
            "/local/data/project", "/erda/projects/myproject", keep_original=True
        )
        self.assertIn('ssh erda mkdir -p "/erda/projects/myproject"', script)
        self.assertIn('rsync -avh --info=progress2 "/local/data/project" "erda:/erda/projects/myproject"/', script)
        self.assertIn("Transfer complete. Source kept.", script)
        self.assertNotIn("rm -rf", script)

    def test_build_move_erda_script_delete_source_on_success(self):
        script = shell.build_move_erda_script(
            "/local/data/project", "/erda/projects/myproject", keep_original=False
        )
        self.assertIn('ssh erda mkdir -p "/erda/projects/myproject"', script)
        self.assertIn('rsync -avh --info=progress2 "/local/data/project" "erda:/erda/projects/myproject"/', script)
        self.assertIn('rm -rf "/local/data/project"', script)
        self.assertIn("Transfer complete. Source deleted.", script)
        self.assertIn("ERROR: Transfer failed. Source was NOT deleted.", script)

    def test_build_move_erda_script_quotes_paths_with_spaces(self):
        script = shell.build_move_erda_script(
            "/local/my project", "/erda/my dest", keep_original=True
        )
        self.assertIn('"/local/my project"', script)
        self.assertIn('"/erda/my dest"', script)
        self.assertIn('"erda:/erda/my dest"/', script)

    def test_build_transfer_ena_script_keep_original_exits_nonzero_on_failure(self):
        script = shell.build_transfer_ena_script("/local/data.fastq.gz", keep_original=True)

        self.assertIn("curl --ftp-ssl", script)
        self.assertIn("Transfer complete. Source kept.", script)
        self.assertIn("ERROR: Transfer failed.", script)
        self.assertIn("exit $UPLOAD_RC", script)
        self.assertNotIn("rm -rf", script)

    def test_build_transfer_ena_script_delete_source_exits_nonzero_on_failure(self):
        script = shell.build_transfer_ena_script("/local/data.fastq.gz", keep_original=False)

        self.assertIn('rm -rf "/local/data.fastq.gz"', script)
        self.assertIn("ERROR: Transfer failed. Source was NOT deleted.", script)
        self.assertIn("exit $UPLOAD_RC", script)

    def test_resolve_project_uses_directory_under_projects(self):
        self.assertEqual(
            shell.resolve_project("/projects/earthhologenome/people/antton"),
            "earthhologenome",
        )

    def test_resolve_project_falls_back_to_default_outside_projects(self):
        self.assertEqual(shell.resolve_project("/home/antton"), shell.DEFAULT_PROJECT)

    def test_resolve_user_prefers_explicit_value(self):
        self.assertEqual(shell.resolve_user("someone"), "someone")

    def test_resolve_user_reads_user_environment_variable(self):
        with mock.patch.dict("os.environ", {"USER": "antton"}, clear=False):
            self.assertEqual(shell.resolve_user(), "antton")

    def test_build_cd_path_home(self):
        self.assertEqual(shell.build_cd_path("home", "alberdilab", "antton"), "/home/antton")

    def test_build_cd_path_people(self):
        self.assertEqual(
            shell.build_cd_path("people", "alberdilab", "antton"),
            "/projects/alberdilab/people",
        )

    def test_build_cd_path_project_is_user_people_directory(self):
        self.assertEqual(
            shell.build_cd_path("project", "alberdilab", "antton"),
            "/projects/alberdilab/people/antton",
        )

    def test_build_cd_path_data(self):
        self.assertEqual(
            shell.build_cd_path("data", "alberdilab", "antton"),
            "/projects/alberdilab/data",
        )

    def test_build_cd_path_scratch_uses_user_directory_when_present(self):
        path = shell.build_cd_path(
            "scratch", "alberdilab", "antton", is_dir=lambda p: True
        )
        self.assertEqual(path, "/projects/alberdilab/scratch/antton")

    def test_build_cd_path_scratch_falls_back_to_shared_directory(self):
        path = shell.build_cd_path(
            "scratch", "alberdilab", "antton", is_dir=lambda p: False
        )
        self.assertEqual(path, "/projects/alberdilab/scratch")

    def test_build_cd_path_rejects_unknown_target(self):
        with self.assertRaises(ValueError):
            shell.build_cd_path("nowhere", "alberdilab", "antton")


if __name__ == "__main__":
    unittest.main()
