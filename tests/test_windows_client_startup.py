"""Windows startup broker must not change privilege or create autorun tasks."""

import subprocess
import tempfile
from pathlib import Path
import sys
import unittest
from unittest import mock

from swcli.windows_client_startup import in_client_job, register_start_task


class StartupBrokerTests(unittest.TestCase):
    def test_posix_never_uses_windows_job_or_scheduler(self):
        with mock.patch("swcli.windows_client_startup.sys.platform", "darwin"):
            self.assertFalse(in_client_job())

    def test_demand_only_same_user_session_task_has_literal_arguments(self):
        service = mock.Mock()
        definition = service.NewTask.return_value
        folder = service.GetFolder.return_value
        arguments = [r"C:\Workspace\中文 目录\bootstrap.py", "--endpoint", "127.0.0.1:19595"]
        actual_folder, running = register_start_task(service, name="SWCLI-demand-known", user_sid="S-1-5-user", arguments=arguments, session_id=2)
        folder.RegisterTaskDefinition.assert_called_once_with("SWCLI-demand-known", definition, 2, "S-1-5-user", None, 3)
        self.assertEqual(definition.Principal.UserId, "S-1-5-user")
        self.assertEqual(definition.Principal.RunLevel, 0)
        self.assertEqual(definition.Principal.LogonType, 3)
        self.assertFalse(definition.Settings.StartWhenAvailable)
        self.assertFalse(definition.Settings.DisallowStartIfOnBatteries)
        self.assertFalse(definition.Settings.StopIfGoingOnBatteries)
        self.assertEqual(definition.Settings.ExecutionTimeLimit, "PT0S")
        definition.Triggers.Create.assert_not_called()
        action = definition.Actions.Create.return_value
        self.assertEqual(action.Path, sys.executable)
        self.assertEqual(action.Arguments, subprocess.list2cmdline(arguments))
        task = folder.RegisterTaskDefinition.return_value
        task.RunEx.assert_called_once_with("", 4, 2, "")
        self.assertIs(actual_folder, folder)
        self.assertIs(running, task.RunEx.return_value)

    def test_failed_task_start_removes_only_its_own_definition(self):
        service = mock.Mock()
        folder = service.GetFolder.return_value
        folder.RegisterTaskDefinition.return_value.RunEx.side_effect = RuntimeError("denied")
        with self.assertRaisesRegex(RuntimeError, "denied"):
            register_start_task(service, name="SWCLI-demand-owned", user_sid="sid", arguments=[], session_id=1)
        folder.DeleteTask.assert_called_once_with("SWCLI-demand-owned", 0)


class BootstrapLoggingTests(unittest.TestCase):
    def test_task_without_console_streams_uses_its_utf8_log_and_restores_them(self):
        from swcli.client_bootstrap import main
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "nested" / "daemon.log"
            def fake_cli(arguments):
                self.assertEqual(arguments, ["daemon", "serve", "--host", "127.0.0.1", "--port", "19100", "--startup-timeout", "120"])
                print("原生宿主 startup")
                print("diagnostic", file=sys.stderr)
                return 7
            with mock.patch.object(sys, "argv", ["bootstrap", "--endpoint", "127.0.0.1:19100", "--startup-timeout", "120", "--log", str(log)]), \
                    mock.patch("swcli.cli.main", side_effect=fake_cli), \
                    mock.patch.object(sys, "stdout", None), mock.patch.object(sys, "stderr", None):
                self.assertEqual(main(), 7)
                self.assertIsNone(sys.stdout)
                self.assertIsNone(sys.stderr)
            self.assertEqual(log.read_text(encoding="utf-8"), "原生宿主 startup\ndiagnostic\n")
