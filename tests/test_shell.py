import unittest

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

    def test_invalid_sort_is_rejected(self):
        with self.assertRaises(ValueError):
            shell.build_list_command(sort_by="date")

    def test_invalid_order_is_rejected(self):
        with self.assertRaises(ValueError):
            shell.build_list_command(order="descending")

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

    def test_blank_conda_environment_name_is_rejected(self):
        with self.assertRaises(ValueError):
            shell.build_conda_create_command("")


if __name__ == "__main__":
    unittest.main()
