"""Background interpreter selection must preserve the selected runtime and logs."""

from pathlib import Path
import os
import tempfile
import unittest
from unittest import mock

from swcli.background_runtime import background_python
from swcli.windows_client_startup import register_start_task
from swcli.daemon.main import start_daemon


class BackgroundRuntimeTests(unittest.TestCase):
    def test_windows_uses_windowed_sibling_in_same_installation(self):
        with tempfile.TemporaryDirectory(prefix="swcli runtime ") as directory:
            console = Path(directory) / "python.exe"
            windowed = Path(directory) / "pythonw.exe"
            windowed.touch()
            with mock.patch("swcli.background_runtime.sys.platform", "win32"), mock.patch("swcli.background_runtime.sys.executable", str(console)):
                self.assertEqual(background_python(), str(windowed))
                windowed.unlink()
                with self.assertRaisesRegex(FileNotFoundError, "pythonw.exe"):
                    background_python()

    def test_posix_and_already_windowed_python_are_unchanged(self):
        for platform, executable in (("darwin", "/usr/bin/python3"), ("win32", "pythonw.exe")):
            with self.subTest(platform=platform), mock.patch("swcli.background_runtime.sys.platform", platform), mock.patch("swcli.background_runtime.sys.executable", executable):
                self.assertEqual(background_python(), executable)

    def test_task_action_uses_windowed_runtime_without_altering_arguments(self):
        service = mock.Mock()
        args = ["bootstrap.py", "--log", "log with spaces.txt"]
        with mock.patch("swcli.windows_client_startup.background_python", return_value="runtime/pythonw.exe"):
            register_start_task(service, name="SWCLI-demand-test", user_sid="sid", arguments=args, session_id=1)
        action = service.NewTask.return_value.Actions.Create.return_value
        self.assertEqual(action.Path, "runtime/pythonw.exe")
        self.assertIn('"log with spaces.txt"', action.Arguments)

    def test_detached_launch_uses_same_windowed_runtime_and_keeps_log(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {"LOCALAPPDATA": directory}), mock.patch("swcli.daemon.main.sys.platform", "win32"), mock.patch("swcli.daemon.main.background_python", return_value="runtime/pythonw.exe"), mock.patch("swcli.daemon.main.call_daemon", side_effect=[ConnectionRefusedError(), {"success": True, "result": {"worker_alive": True}}]), mock.patch("swcli.daemon.main.subprocess.Popen") as popen:
            result = start_daemon(endpoint="127.0.0.1:19000")
            self.assertTrue(result["success"])
            self.assertEqual(popen.call_args.args[0][0], "runtime/pythonw.exe")
            self.assertTrue(popen.call_args.kwargs["stdout"].closed)
            self.assertTrue(Path(result["result"]["log"]).is_file())

    def test_missing_windowed_runtime_never_launches_or_changes_first_error(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {"LOCALAPPDATA": directory}), mock.patch("swcli.daemon.main.sys.platform", "win32"), mock.patch("swcli.daemon.main.background_python", side_effect=FileNotFoundError("missing pythonw.exe")), mock.patch("swcli.daemon.main.call_daemon", side_effect=ConnectionRefusedError()), mock.patch("swcli.daemon.main.subprocess.Popen") as popen:
            result = start_daemon(endpoint="127.0.0.1:19000")
            self.assertFalse(result["success"])
            self.assertEqual(result["error"]["code"], "FileNotFoundError")
            popen.assert_not_called()
