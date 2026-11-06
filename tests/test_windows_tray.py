"""Tray policy/control tests; an optional native Shell gate never starts SW."""
import contextlib
import io
import json
import os
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli import windows_tray as tray
from swcli.cli import build_parser
from swcli.daemon_manager import DaemonManager


class PolicyTests(unittest.TestCase):
    def test_auto_native_on_wine_off_and_explicit_choice_wins(self):
        with mock.patch.object(tray.sys, "platform", "win32"), mock.patch.object(tray, "is_wine", return_value=False):
            self.assertTrue(tray.tray_enabled("auto"))
            self.assertFalse(tray.tray_enabled("auto", "linux-wine"))
            self.assertFalse(tray.tray_enabled("auto", "macos-wine"))
            self.assertFalse(tray.tray_enabled("off"))
            self.assertTrue(tray.tray_enabled("on", "linux-wine"))
        with mock.patch.object(tray.sys, "platform", "win32"), mock.patch.object(tray, "is_wine", return_value=True):
            self.assertFalse(tray.tray_enabled("auto"))
        with mock.patch.object(tray.sys, "platform", "darwin"):
            self.assertFalse(tray.tray_enabled("auto"))
            with self.assertRaisesRegex(RuntimeError, "Windows execution runtime"):
                tray.tray_enabled("on")

    def test_off_never_imports_or_constructs_windows_gui(self):
        with mock.patch.object(tray, "TrayController") as controller, mock.patch.object(tray, "is_wine") as wine:
            self.assertIsNone(tray.start_tray("off", endpoint="127.0.0.1:19495"))
        controller.assert_not_called(); wine.assert_not_called()

    def test_auto_failure_is_stderr_only_and_explicit_on_reports_failure(self):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(tray, "tray_enabled", return_value=True), \
                mock.patch.object(tray, "TrayController", side_effect=RuntimeError("no notification area")), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            self.assertIsNone(tray.start_tray("auto", endpoint="127.0.0.1:19495"))
            with self.assertRaisesRegex(RuntimeError, "requested Windows tray"):
                tray.start_tray("on", endpoint="127.0.0.1:19495")
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(json.loads(errors.getvalue())["event"], "tray.unavailable")

    def test_parser_choices_are_independent_of_sw_visibility(self):
        parser = build_parser()
        for command in ("start", "serve", "restart"):
            self.assertEqual(parser.parse_args(["daemon", command]).tray, "auto")
            args = parser.parse_args(["daemon", command, "--tray", "off", "--visible"])
            self.assertEqual(args.tray, "off"); self.assertTrue(args.visible)
        with self.assertRaises(ValueError):
            tray.validate_mode("sometimes")

    def test_reuse_does_not_spawn_an_icon_or_change_existing_daemon(self):
        manager = DaemonManager(host_launcher=None)
        with mock.patch.object(manager, "_call", return_value={"success": True, "result": {
                "worker_alive": True, "host_connected": True}}), mock.patch.object(tray, "TrayController") as icon:
            self.assertTrue(manager.start(tray="off")["result"]["already_running"])
        icon.assert_not_called()

    def test_native_and_job_start_forward_explicit_mode(self):
        manager = DaemonManager(host_launcher="")
        offline = ConnectionRefusedError("offline"); offline._swcli_transport_phase = "connect"
        with mock.patch.object(manager, "_call", side_effect=offline), \
                mock.patch("swcli.daemon_manager.sys.platform", "win32"), \
                mock.patch("swcli.windows_client_startup.in_client_job", return_value=True), \
                mock.patch("swcli.windows_client_startup.start_resident_daemon", return_value={"success": True}) as start:
            self.assertTrue(manager.start(tray="off")["success"])
        self.assertEqual(start.call_args.kwargs["tray"], "off")

    def test_explicit_on_failure_is_structured_before_any_sw_worker_is_created(self):
        from swcli.daemon import main as lifecycle
        args = build_parser().parse_args(["daemon", "serve", "--tray", "on"])
        output = io.StringIO()
        with mock.patch.object(tray, "start_tray", side_effect=RuntimeError("no notification area")), \
                mock.patch.object(lifecycle, "SwclidServer") as server, \
                mock.patch.object(lifecycle, "WorkerManager") as worker, contextlib.redirect_stdout(output):
            self.assertEqual(lifecycle.run(args), 1)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "TrayUnavailable")
        worker.assert_not_called(); server.return_value.server_close.assert_called_once()

    def test_native_startup_failure_removes_only_the_icon(self):
        from swcli.daemon import main as lifecycle
        controller = mock.Mock()
        args = build_parser().parse_args(["daemon", "serve", "--tray", "on"])
        with mock.patch.object(tray, "start_tray", return_value=controller), \
                mock.patch.object(lifecycle, "SwclidServer"), \
                mock.patch.object(lifecycle, "WorkerManager", side_effect=lifecycle.WorkerStartupError("ExistingHostRequiresAttach", "attach explicitly")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(lifecycle.run(args), 1)
        controller.close.assert_called_once(); controller.ready.assert_not_called()

    def test_mcp_forwards_the_same_explicit_mode_and_rejects_unknown_modes(self):
        from swcli.mcp import DaemonBridge
        with mock.patch("swcli.mcp.DaemonManager") as manager:
            manager.return_value.start.return_value = {"success": True}
            bridge = DaemonBridge()
            self.assertTrue(bridge.call("daemon_start", {"tray": "off"})["success"])
            manager.return_value.start.assert_called_once_with(tray="off")
            self.assertFalse(bridge.call("daemon_start", {"tray": "sometimes"})["success"])
            self.assertEqual(manager.return_value.start.call_count, 1)

    def test_external_host_utilities_receive_the_explicit_icon_mode_literally(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / "utilities with spaces"
            launcher.touch(); launcher.chmod(0o700)
            manager = DaemonManager(host_launcher=str(launcher))
            offline = ConnectionRefusedError("offline"); offline._swcli_transport_phase = "connect"
            ready = {"success": True, "result": {"worker_alive": True, "host_connected": True}}
            def utility(*args, **kwargs):
                kwargs["stdout"].write(b'{"success":true}')
                return mock.Mock(returncode=0)
            with mock.patch.object(manager, "_call", side_effect=[offline, ready]), \
                    mock.patch("swcli.daemon_manager.sys.platform", "darwin"), \
                    mock.patch("swcli.daemon_manager.subprocess.run", side_effect=utility) as run:
                self.assertTrue(manager.start(tray="off")["success"])
            self.assertEqual(run.call_args.args[0][-2:], ["--tray", "off"])
            self.assertFalse(run.call_args.kwargs.get("shell", False))

    def test_bootstrap_preserves_mode_without_reinterpreting_it(self):
        import tempfile
        from pathlib import Path
        from swcli.client_bootstrap import main
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(sys, "argv", ["bootstrap", "--endpoint", "127.0.0.1:19495", "--startup-timeout", "120", "--log", str(Path(directory) / "daemon.log"), "--tray", "off"]), \
                mock.patch("swcli.cli.main", return_value=0) as cli:
            self.assertEqual(main(), 0)
        self.assertEqual(cli.call_args.args[0][-2:], ["--tray", "off"])


class FakeView:
    def __init__(self, controller):
        self.controller = controller
        self.messages = []
        self.received = threading.Event()
        self.closed = False
    def run(self, created, closed):
        created.set(); closed.wait(2)
    def post(self, action, value):
        self.messages.append((action, value)); self.received.set()
    def close(self):
        self.closed = True


class ControllerTests(unittest.TestCase):
    def controller(self):
        manager = mock.Mock()
        controller = tray.TrayController("127.0.0.1:19495", view_factory=FakeView,
                                        manager_factory=mock.Mock(return_value=manager))
        controller.start()
        self.addCleanup(controller.close)
        return controller, manager, controller._view

    def test_ready_and_hide_do_not_query_or_stop_sw(self):
        controller, manager, view = self.controller()
        controller.ready(); controller.close()
        manager.status.assert_not_called(); manager.stop.assert_not_called()
        self.assertTrue(view.closed)
        self.assertEqual(view.messages, [("ready", None)])

    def test_shutdown_refusal_is_retained_with_one_request_and_no_force_path(self):
        controller, manager, view = self.controller()
        refused = {"success": False, "error": {"code": "OpenDocuments", "message": "close explicitly"}}
        manager.stop.return_value = refused
        controller.ready(); view.received.clear()
        self.assertTrue(controller.request("stop")); self.assertTrue(view.received.wait(2))
        self.assertEqual(view.messages[-1], ("stop", refused))
        manager.stop.assert_called_once_with(); manager.status.assert_not_called()
        self.assertFalse(controller._closed.is_set())

    def test_pending_stop_blocks_duplicate_click_and_hiding_does_not_cancel_or_retry_it(self):
        controller, manager, view = self.controller()
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        def stop():
            entered.set(); release.wait(2); finished.set()
            return {"success": True}
        manager.stop.side_effect = stop
        controller.ready(); self.assertTrue(controller.request("stop")); self.assertTrue(entered.wait(2))
        self.assertFalse(controller.request("stop"))
        controller.close(); release.set(); self.assertTrue(finished.wait(2))
        manager.stop.assert_called_once_with()
        self.assertNotIn("stop", [name for name, value in view.messages])

    def test_starting_and_closed_tray_accept_no_requests(self):
        controller, manager, view = self.controller()
        self.assertFalse(controller.request("stop"))
        controller.ready(); controller.close()
        self.assertFalse(controller.request("status"))
        manager.stop.assert_not_called(); manager.status.assert_not_called()

    def test_status_preserves_unknown_and_user_host_ownership(self):
        text = tray.status_text({"success": True, "result": {"daemon_state": "ready",
             "daemon_sw_pid": 123, "daemon_sw_owned": False, "daemon_sw_visible": None,
             "user_sw_running": True}}, "127.0.0.1:19495")
        self.assertIn("附加的用户宿主", text); self.assertIn("SW 窗口可见: 未知", text)
        self.assertIn("用户 SW 正在运行: 是", text)


class TrayActivationTests(unittest.TestCase):
    def test_activation_never_queries_status_and_context_click_opens_only_menu(self):
        controller = mock.Mock()
        view = tray.Win32TrayView(controller)
        view.con = mock.Mock(WM_RBUTTONUP=0x205, WM_CONTEXTMENU=0x7b)
        with mock.patch.object(view, "_menu") as menu:
            for event in (0x202, 0x203, 0x400, 0x401):
                self.assertEqual(view._notify(1, view.CALLBACK, 1, event), 0)
            menu.assert_not_called()
            controller.request.assert_not_called()
            for event in (0x205, 0x7b):
                view._notify(1, view.CALLBACK, 1, event)
            self.assertEqual(menu.call_count, 2)
            controller.request.assert_not_called()


@unittest.skipUnless(sys.platform == "win32", "Native Shell icon gate; no SW or COM call")
class NativeNotificationAreaTests(unittest.TestCase):
    def test_real_icon_exists_then_is_removed_without_starting_a_daemon(self):
        import ctypes
        from ctypes import wintypes
        import pywintypes
        import win32gui
        if tray.is_wine() or not win32gui.FindWindow("Shell_TrayWnd", None):
            self.skipTest("No native interactive Windows taskbar; desktop acceptance remains pending")
        class GUID(ctypes.Structure):
            _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
        class Identifier(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT), ("guidItem", GUID)]
        api = ctypes.WinDLL("shell32").Shell_NotifyIconGetRect
        api.argtypes = [ctypes.POINTER(Identifier), ctypes.POINTER(wintypes.RECT)]
        api.restype = ctypes.c_long
        manager = mock.Mock()
        controller = tray.TrayController("127.0.0.1:19495", manager_factory=mock.Mock(return_value=manager))
        try:
            controller.start()
            identifier = Identifier(ctypes.sizeof(Identifier), controller._view.hwnd, 1, GUID())
            rect = wintypes.RECT()
            location_result = api(ctypes.byref(identifier), ctypes.byref(rect))
            if location_result == 0:
                self.assertGreater(rect.right, rect.left)
            # Explorer normally puts new icons in its collapsed overflow area.
            # GetRect need not expose a usable rectangle until that area opens.
            # NIM_MODIFY succeeds only for the existing registered identifier;
            # do not promote an icon or alter the user's notification settings.
            registered = (controller._view.hwnd, 1, win32gui.NIF_TIP, 0, 0,
                          "SWCLI native notification icon verification")
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, registered)
            controller.close()
            self.assertFalse(controller._thread.is_alive())
            self.assertNotEqual(api(ctypes.byref(identifier), ctypes.byref(rect)), 0)
            with self.assertRaises(pywintypes.error):
                win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, registered)
            print(json.dumps({"event": "native.tray.registration", "registered": True,
                              "location_hresult": location_result, "removed": True}))
        finally:
            controller.close()
        manager.status.assert_not_called(); manager.stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
