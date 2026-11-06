"""Windows startup broker must not change privilege or create autorun tasks."""

import subprocess
import contextlib
import os
from types import ModuleType
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


class ResidentStartupResultsTests(unittest.TestCase):
    @contextlib.contextmanager
    def broker(self, directory, *, state=3):
        from swcli import windows_client_startup as broker
        client = mock.Mock()
        parent = ModuleType("win32com"); parent.client = client
        security = mock.Mock()
        security.GetTokenInformation.return_value = ("user-token",)
        modules = {"pythoncom": mock.Mock(), "win32api": mock.Mock(),
                   "win32con": mock.Mock(TOKEN_QUERY=8), "win32security": security,
                   "win32com": parent, "win32com.client": client}
        folder, running = mock.Mock(), mock.Mock(State=state)
        def session_id(pid, output):
            output._obj.value = 1
            return True
        dll = mock.Mock()
        dll.ProcessIdToSessionId.side_effect = session_id
        with mock.patch.dict(sys.modules, modules), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": directory}), \
                mock.patch("ctypes.WinDLL", return_value=dll, create=True), \
                mock.patch.object(broker, "register_start_task", return_value=(folder, running)) as register, \
                mock.patch("swcli.daemon.client.call_daemon", side_effect=ConnectionRefusedError), \
                mock.patch("swcli.daemon.main._read_startup_failure", return_value={
                    "code": "ExistingHostNotFound", "message": "attach requires an existing instance"}), \
                mock.patch("swcli.daemon.main._read_startup_host", return_value=None), \
                mock.patch.object(broker.subprocess, "run") as kill:
            yield broker, folder, running, register, kill
        modules["pythoncom"].CoUninitialize.assert_called_once()

    def test_expected_refusal_returns_original_json_and_does_not_stop_finished_task(self):
        with tempfile.TemporaryDirectory() as directory, self.broker(directory) as (broker, folder, running, register, kill):
            value = broker.start_resident_daemon(endpoint="127.0.0.1:19495", startup_timeout_seconds=120,
                                                  attach_existing=True)
            self.assertFalse(value["success"])
            self.assertEqual(value["error"]["code"], "ExistingHostNotFound")
            self.assertNotIn("cleanup_errors", value)
            running.Stop.assert_not_called()
            kill.assert_not_called()
            folder.DeleteTask.assert_called_once_with(register.call_args.kwargs["name"], 0)
            self.assertIn("--attach-existing", register.call_args.kwargs["arguments"])

    def test_task_exiting_between_state_and_stop_is_a_benign_cleanup_race(self):
        # Exact native COM wrapper shape from CI: DISP_E_EXCEPTION with a nested
        # SCHED_E_TASK_NOT_RUNNING, not every COM error or every failed Stop.
        error = Exception("task already finished")
        error.hresult = -2147352567
        error.excepinfo = (0, None, None, None, 0, -2147216629)
        with tempfile.TemporaryDirectory() as directory, self.broker(directory, state=4) as (broker, folder, running, register, kill):
            running.Stop.side_effect = error
            value = broker.start_resident_daemon(endpoint="127.0.0.1:19495", startup_timeout_seconds=120,
                                                  attach_existing=True)
            self.assertEqual(value["error"]["code"], "ExistingHostNotFound")
            self.assertNotIn("cleanup_errors", value)
            running.Stop.assert_called_once()
            register.assert_called_once()
            kill.assert_not_called()

    def test_cleanup_failure_is_reported_without_hiding_refusal_or_retrying(self):
        with tempfile.TemporaryDirectory() as directory, self.broker(directory, state=4) as (broker, folder, running, register, kill):
            running.Stop.side_effect = PermissionError("task stop denied")
            folder.DeleteTask.side_effect = PermissionError("definition delete denied")
            value = broker.start_resident_daemon(endpoint="127.0.0.1:19495", startup_timeout_seconds=120,
                                                  attach_existing=True)
            self.assertEqual(value["error"]["code"], "ExistingHostNotFound")
            self.assertEqual([row["stage"] for row in value["cleanup_errors"]], ["task.stop", "task.delete"])
            running.Stop.assert_called_once()
            folder.DeleteTask.assert_called_once()
            register.assert_called_once()
            kill.assert_not_called()

    def test_ready_resident_is_preserved_when_its_task_definition_is_deleted(self):
        with tempfile.TemporaryDirectory() as directory, self.broker(directory, state=4) as (broker, folder, running, register, kill):
            health = {"success": True, "result": {"host_connected": True, "worker_alive": True}}
            with mock.patch("swcli.daemon.client.call_daemon", return_value=health):
                value = broker.start_resident_daemon(endpoint="127.0.0.1:19495", startup_timeout_seconds=120)
            self.assertTrue(value["success"])
            running.Stop.assert_not_called()
            kill.assert_not_called()
            folder.DeleteTask.assert_called_once()

    def test_failed_attachment_never_terminates_a_shared_user_host(self):
        with tempfile.TemporaryDirectory() as directory, self.broker(directory, state=4) as (broker, folder, running, register, kill):
            with mock.patch("swcli.daemon.main._read_startup_host", return_value={
                    "owned_by_daemon": False, "process_id": 4321}):
                value = broker.start_resident_daemon(endpoint="127.0.0.1:19495", startup_timeout_seconds=120,
                                                      attach_existing=True)
            self.assertEqual(value["error"]["code"], "ExistingHostNotFound")
            running.Stop.assert_called_once()
            kill.assert_not_called()
