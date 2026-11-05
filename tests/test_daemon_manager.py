import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from swcli import PROTOCOL_VERSION
from swcli.cli import main, build_parser
from swcli.daemon_manager import DaemonManager
from swcli.runtime_state import snapshot


def response(result=None, **fields):
    return {"api_version": PROTOCOL_VERSION, "request_id": "request-1", "success": True,
            "duration_ms": 0, "result": result if result is not None else {}, **fields}


def ready():
    return response({"worker_alive": True, "host_connected": True, "host": {"process_id": 10, "visible": False, "owned_by_daemon": True}})


def offline(error_type=ConnectionRefusedError):
    error = error_type("offline")
    error._swcli_transport_phase = "connect"
    return error


class DaemonManagerTests(unittest.TestCase):
    def setUp(self):
        environment = mock.patch.dict(os.environ, {}, clear=True)
        environment.start(); self.addCleanup(environment.stop)
        job = mock.patch("swcli.windows_client_startup.in_client_job", return_value=False)
        job.start(); self.addCleanup(job.stop)
        self.manager = DaemonManager()

    def test_detailed_status_uses_executor_observation_and_never_starts(self):
        value = snapshot({"host_connected": True, "host": {"process_id": 10, "owned_by_daemon": True, "visible": False}})
        with mock.patch.object(self.manager, "_call", return_value=response(value)) as call, mock.patch("swcli.daemon.main.start_daemon") as start:
            self.assertEqual(self.manager.status()["result"], value)
        call.assert_called_once_with("daemon.runtime-status")
        start.assert_not_called()

    def test_offline_local_and_remote_do_not_confuse_client_inventory(self):
        for endpoint, expected_calls in (("127.0.0.1:18495", 1), ("192.0.2.1:18495", 0)):
            manager = DaemonManager(endpoint=endpoint)
            with mock.patch.object(manager, "_call", side_effect=offline()), mock.patch("swcli.daemon_manager.native_inventory", return_value={"processes": [], "pid_namespace": "windows", "errors": []}) as inventory:
                value = manager.status()["result"]
            self.assertFalse(value["daemon_running"])
            self.assertEqual(inventory.call_count, expected_calls)
            if not expected_calls:
                self.assertIsNone(value["sw_running"])

    def test_connect_timeout_or_lost_reply_is_not_definitely_stopped(self):
        for error in (offline(TimeoutError), ConnectionResetError("lost reply")):
            with self.subTest(error=error), mock.patch.object(self.manager, "_call", side_effect=error), mock.patch("swcli.daemon_manager.native_inventory", return_value={"processes": None, "pid_namespace": "unavailable", "errors": []}):
                self.assertIsNone(self.manager.status()["result"]["daemon_running"])

    def test_old_daemon_has_read_only_health_fallback_without_current_visibility_claim(self):
        unsupported = response(success=False, error={"code": "ValueError", "message": "unsupported operation: daemon.runtime-status"})
        with mock.patch.object(self.manager, "_call", side_effect=[unsupported, ready()]) as call:
            value = self.manager.status()["result"]
        self.assertEqual(call.call_count, 2)
        self.assertFalse(value["visibility_current"])
        self.assertEqual(value["probe_errors"][0]["code"], "RuntimeObservationUnavailable")

    def test_ready_daemon_reuse_never_invokes_host_launcher_or_changes_visibility(self):
        self.manager.host_launcher = "/not/executed"
        with mock.patch.object(self.manager, "_call", return_value=ready()), mock.patch("swcli.daemon_manager.subprocess.run") as run:
            value = self.manager.start(visible=True)
        self.assertTrue(value["result"]["already_running"])
        self.assertFalse(value["result"]["health"]["host"]["visible"])
        run.assert_not_called()

    def test_unhealthy_existing_daemon_is_not_automatically_restarted(self):
        with mock.patch.object(self.manager, "_call", return_value=response({"host_connected": False, "worker_alive": True})), mock.patch("swcli.daemon.main.start_daemon") as start:
            value = self.manager.start()
        self.assertEqual(value["error"]["code"], "HostNotReady")
        start.assert_not_called()

    def test_posix_without_host_launcher_does_not_spawn_its_own_python(self):
        with mock.patch.object(self.manager, "_call", side_effect=offline()), mock.patch("swcli.daemon_manager.sys.platform", "darwin"), mock.patch("swcli.daemon.main.start_daemon") as start:
            value = self.manager.start()
        self.assertEqual(value["error"]["code"], "HostLauncherRequired")
        start.assert_not_called()

    def test_explicit_launcher_overrides_environment(self):
        with mock.patch.dict(os.environ, {"SWCLI_DAEMON_UTILS": "/environment/launcher"}):
            self.assertEqual(DaemonManager().host_launcher, "/environment/launcher")
            self.assertEqual(DaemonManager(host_launcher="/explicit/launcher").host_launcher, "/explicit/launcher")

    def test_invalid_configured_launcher_never_falls_back_to_native(self):
        manager = DaemonManager(host_launcher="relative-host")
        with mock.patch.object(manager, "_call", side_effect=offline()), mock.patch("swcli.daemon_manager.sys.platform", "darwin"), mock.patch("swcli.daemon.main.start_daemon") as native:
            self.assertEqual(manager.start()["error"]["code"], "InvalidHostLauncher")
        native.assert_not_called()

    def test_remote_endpoint_never_executes_local_launcher(self):
        manager = DaemonManager(endpoint="192.0.2.1:18495", host_launcher="/host/launcher")
        with mock.patch.object(manager, "_call", side_effect=offline()), mock.patch("swcli.daemon_manager.subprocess.run") as run:
            self.assertEqual(manager.start()["error"]["code"], "NonLocalEndpoint")
        run.assert_not_called()

    def test_host_launcher_receives_literal_args_environment_and_separate_posix_session(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / "宿主 launcher"
            launcher.touch(); launcher.chmod(0o700)
            manager = DaemonManager(host_launcher=str(launcher))
            result = {"success": True, "result": {"started": True}}
            with mock.patch.object(manager, "_call", side_effect=[offline(), ready()]), mock.patch("swcli.daemon_manager.sys.platform", "darwin"), mock.patch("swcli.daemon_manager.subprocess.run", return_value=mock.Mock(returncode=0, stdout=json.dumps(result).encode())) as run, mock.patch("swcli.daemon.main.start_daemon") as native:
                self.assertTrue(manager.start(visible=True, attach_existing=True, startup_timeout_seconds=300)["success"])
            argv = run.call_args.args[0]
            self.assertEqual(argv, [str(launcher), "start", "--endpoint", "127.0.0.1:18495", "--startup-timeout", "300.0", "--json", "--visible", "--attach-existing"])
            self.assertTrue(run.call_args.kwargs["start_new_session"])
            self.assertEqual(run.call_args.kwargs["env"]["SWCLI_DAEMON_UTILS_ACTIVE"], "1")
            self.assertFalse(run.call_args.kwargs.get("shell", False))
            native.assert_not_called()

    def test_delegated_windows_backend_does_not_recurse_into_host_launcher_or_scheduler(self):
        self.manager.host_launcher = "/must-not-run"
        with mock.patch.dict(os.environ, {"SWCLI_DAEMON_UTILS_ACTIVE": "1"}), mock.patch.object(self.manager, "_call", side_effect=offline()), mock.patch("swcli.daemon_manager.sys.platform", "win32"), mock.patch("swcli.daemon.main.start_daemon", return_value={"success": True}) as native, mock.patch("swcli.daemon_manager.subprocess.run") as external:
            self.assertTrue(self.manager.start()["success"])
        native.assert_called_once_with(endpoint="127.0.0.1:18495", startup_timeout_seconds=120.0, visible=False, attach_existing=False)
        external.assert_not_called()

    def test_native_windows_mcp_job_uses_independent_broker(self):
        with mock.patch.object(self.manager, "_call", side_effect=offline()), mock.patch("swcli.daemon_manager.sys.platform", "win32"), mock.patch("swcli.windows_client_startup.in_client_job", return_value=True), mock.patch("swcli.windows_client_startup.start_resident_daemon", return_value={"success": True}) as broker:
            self.assertTrue(self.manager.start(visible=True)["success"])
        broker.assert_called_once_with(endpoint="127.0.0.1:18495", startup_timeout_seconds=120.0, visible=True, attach_existing=False)

    def test_external_timeout_is_unknown_and_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher=Path(directory)/"launcher"; launcher.touch(); launcher.chmod(0o700)
            manager=DaemonManager(host_launcher=str(launcher))
            with mock.patch.object(manager,"_call",side_effect=offline()), mock.patch("swcli.daemon_manager.sys.platform","darwin"), mock.patch("swcli.daemon_manager.subprocess.run",side_effect=subprocess.TimeoutExpired("launcher",150)) as run:
                value=manager.start()
        self.assertTrue(value["outcome_unknown"])
        run.assert_called_once()

    def test_shutdown_refusal_is_preserved_and_does_not_spawn_or_retry(self):
        refused=response(success=False,error={"code":"ActiveDocument","message":"close explicitly"})
        with mock.patch.object(self.manager,"_call",return_value=refused) as call, mock.patch("swcli.daemon.main.start_daemon") as start:
            self.assertEqual(self.manager.stop(request_id="stop-once"),refused)
        call.assert_called_once_with("daemon.shutdown",timeout=600,request_id="stop-once")
        start.assert_not_called()

    def test_global_options_are_parsed_before_host_only_delegation(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / "daemon utils"; launcher.touch(); launcher.chmod(0o700)
            with mock.patch("swcli.daemon_manager.subprocess.run", return_value=mock.Mock(returncode=17)) as run:
                code = main(["--daemon-utils", str(launcher), "--endpoint", "127.0.0.1:19500", "doctor", "--json"])
            self.assertEqual(code, 17)
            self.assertEqual(run.call_args.args[0], [str(launcher), "doctor", "--json"])
            self.assertEqual(run.call_args.kwargs["env"]["SWCLI_ENDPOINT"], "127.0.0.1:19500")
            self.assertEqual(run.call_args.kwargs["env"]["SWCLI_DAEMON_UTILS_ACTIVE"], "1")

    def test_utils_do_not_intercept_status_stop_or_typed_operations(self):
        manager = DaemonManager(host_launcher="/not/executed")
        for command in (["daemon", "status", "--json"], ["daemon", "stop", "--json"], ["document", "list", "--json"]):
            with self.subTest(command=command), mock.patch("swcli.daemon_manager.subprocess.run") as run:
                self.assertIsNone(manager.forward_host_command(build_parser().parse_args(command)))
                run.assert_not_called()

    def test_serve_and_restart_forward_explicit_actions_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory)/"utils"; launcher.touch(); launcher.chmod(0o700)
            manager = DaemonManager(host_launcher=str(launcher))
            # A new POSIX session keeps resident Wine outside the client's kill
            # group. Windows has no POSIX session; its startup broker is separate.
            for platform, sessions in (
                ("win32", {"serve": False, "restart": False}),
                ("darwin", {"serve": False, "restart": True}),
                ("linux", {"serve": False, "restart": True}),
            ):
                for command in (["daemon", "serve", "--host-platform", "macos-wine", "--port", "19501", "--visible"], ["daemon", "restart", "--attach-existing", "--json"]):
                    with self.subTest(platform=platform, action=command[1]), \
                            mock.patch("swcli.daemon_manager.sys.platform", platform), \
                            mock.patch("swcli.daemon_manager.subprocess.run", return_value=mock.Mock(returncode=0)) as run:
                        self.assertEqual(manager.forward_host_command(build_parser().parse_args(command)),0)
                    argv = run.call_args.args[0]
                    self.assertEqual(argv[:2], [str(launcher), command[1]])
                    self.assertFalse(run.call_args.kwargs.get("shell",False))
                    self.assertIs(run.call_args.kwargs["start_new_session"], sessions[command[1]])
                    self.assertIn("--visible" if command[1]=="serve" else "--attach-existing",argv)

    def test_detailed_cli_uses_same_manager_snapshot(self):
        value={"success":True,"result":snapshot(daemon_running=False,reachable=False)}
        output=io.StringIO()
        with mock.patch("swcli.daemon_manager.DaemonManager.status",return_value=value), contextlib.redirect_stdout(output):
            self.assertEqual(main(["daemon","status","--details","--json"]),0)
        self.assertEqual(json.loads(output.getvalue()),value)
