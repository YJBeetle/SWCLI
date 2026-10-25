"""Offline native-control safety checks, not SOLIDWORKS runtime acceptance."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import weakref


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci/diagnose-native-drawing.py"
spec = importlib.util.spec_from_file_location("native_drawing_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ComError(Exception):
    def __init__(self, hresult):
        self.hresult = hresult


class Drawing:
    GetTitle = "drawing.SLDDRW"
    GetType = 3
    GetPathName = r"C:\private\drawing.SLDDRW"


class NativeDrawingProbeTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.opens = []
        self.references = []
        self.app = SimpleNamespace(GetProcessID=lambda: 123, StartupProcessCompleted=True,
                                   Visible=False, RevisionNumber="32.0", CommandInProgress=False,
                                   GetDocumentCount=lambda: 0, ExitApp=Mock())
        def opened(*args):
            self.opens.append(args)
            document = Drawing()
            self.references.append(weakref.ref(document))
            return document
        def closed(title):
            self.assertIsNone(self.references[-1](), "OpenDoc6 return was retained across CloseDoc")
            self.assertEqual(title, Drawing.GetTitle)
        self.app.OpenDoc6 = Mock(side_effect=opened)
        self.app.CloseDoc = Mock(side_effect=closed)
        self.client = SimpleNamespace(GetActiveObject=Mock(side_effect=ComError(-2147221021)),
                                      DispatchEx=Mock(return_value=self.app),
                                      VARIANT=lambda flags, initial: SimpleNamespace(value=initial))
        self.com = SimpleNamespace(com_error=ComError, VT_BYREF=16384, VT_I4=3, PumpWaitingMessages=Mock())

    def run_direct(self):
        probe.direct_roundtrip(self.client, self.com, Drawing.GetPathName, self.events.append)

    def test_same_host_two_writable_opens_release_before_close_without_save_or_inspect(self):
        self.run_direct()
        self.assertEqual(len(self.opens), 2)
        self.assertEqual([args[:4] for args in self.opens], [(Drawing.GetPathName, 3, 1, "")] * 2)
        self.assertEqual(self.app.CloseDoc.call_count, 2)
        self.client.DispatchEx.assert_called_once_with("SldWorks.Application")
        self.app.ExitApp.assert_called_once()
        self.com.PumpWaitingMessages.assert_not_called()
        self.assertFalse(self.app.CommandInProgress)
        probe.validate_receipt({"events": self.events, "host": next(e for e in self.events if e["event"] == "host-acquired")})

    def test_existing_rot_host_is_not_adopted_or_exited(self):
        self.client.GetActiveObject.side_effect = None
        self.client.GetActiveObject.return_value = self.app
        with self.assertRaisesRegex(RuntimeError, "existing COM host"):
            self.run_direct()
        self.client.DispatchEx.assert_not_called()
        self.app.ExitApp.assert_not_called()

    def test_unknown_rot_error_does_not_launch(self):
        self.client.GetActiveObject.side_effect = ComError(-1)
        with self.assertRaises(ComError):
            self.run_direct()
        self.client.DispatchEx.assert_not_called()

    def test_first_open_failure_is_not_retried(self):
        self.app.OpenDoc6.side_effect = RuntimeError("first failed")
        with self.assertRaisesRegex(RuntimeError, "first failed"):
            self.run_direct()
        self.assertEqual(self.app.OpenDoc6.call_count, 1)
        self.app.CloseDoc.assert_not_called()
        self.app.ExitApp.assert_called_once()

    def test_second_open_failure_is_not_retried(self):
        original = self.app.OpenDoc6.side_effect
        def opened(*args):
            if self.opens:
                raise RuntimeError("second failed")
            return original(*args)
        self.app.OpenDoc6.side_effect = opened
        with self.assertRaisesRegex(RuntimeError, "second failed"):
            self.run_direct()
        self.assertEqual(self.app.OpenDoc6.call_count, 2)
        self.app.CloseDoc.assert_called_once()

    def test_cleanup_failure_does_not_mask_native_failure(self):
        self.app.OpenDoc6.side_effect = RuntimeError("native failed")
        self.app.ExitApp.side_effect = RuntimeError("cleanup failed")
        with self.assertRaisesRegex(RuntimeError, "native failed"):
            self.run_direct()
        self.assertEqual([e["event"] for e in self.events if "error" in e], ["case-error", "cleanup-error"])

    def test_close_must_leave_zero_documents(self):
        self.app.GetDocumentCount = Mock(side_effect=[0, 1])
        with self.assertRaisesRegex(RuntimeError, "left open documents"):
            self.run_direct()
        self.assertEqual(self.app.OpenDoc6.call_count, 1)

    def test_warnings_fail_closed_without_retry(self):
        self.client.VARIANT = lambda flags, initial: SimpleNamespace(value=1)
        with self.assertRaisesRegex(RuntimeError, "failed or warned"):
            self.run_direct()
        self.assertEqual(self.app.OpenDoc6.call_count, 1)

    def test_receipt_rejects_missing_or_different_host_second_open(self):
        self.run_direct()
        host = next(e for e in self.events if e["event"] == "host-acquired")
        opened = [e for e in self.events if e["event"] == "opened"]
        opened[1]["process_id"] = 999
        with self.assertRaisesRegex(RuntimeError, "same-host"):
            probe.validate_receipt({"events": self.events, "host": host})

    def test_process_inventory_is_exact_and_unavailable_inventory_is_not_empty(self):
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(stdout='"SLDWORKS.exe","42","Console"\n"other.exe","9","Console"')):
            self.assertEqual(probe.native_pids(), [42])
        for output in ("", "ERROR: inventory failed", '"sldworks.exe","bad"'):
            with self.subTest(output=output), patch.object(probe.subprocess, "run", return_value=SimpleNamespace(stdout=output)):
                with self.assertRaises(RuntimeError):
                    probe.native_pids()

    def test_normal_shutdown_can_settle_without_new_native_request(self):
        with patch.object(probe, "native_pids", side_effect=[[123], []]), patch.object(probe.time, "sleep"):
            self.assertEqual(probe.wait_for_exit(123, sleep=Mock()), [])

    def test_non_ci_or_non_windows_execution_refused(self):
        with patch.dict(probe.os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(RuntimeError, "restricted"):
                probe.run(SimpleNamespace())

    def test_budgets_cannot_be_increased_or_nonfinite(self):
        for request, startup in ((601, 300), (600, 301), (float("nan"), 300), (600, 0)):
            with self.subTest(request=request, startup=startup), patch.object(probe.sys, "platform", "win32"), patch.dict(probe.os.environ, {"GITHUB_ACTIONS": "true"}):
                with self.assertRaises(ValueError):
                    probe.run(SimpleNamespace(request_timeout=request, startup_timeout=startup))

    def test_supervisor_records_stalled_second_call_and_preserves_first_failure(self):
        for earlier in (False, True):
            now = [0.0]
            events = iter([{"event": "ready"}, {"event": "native-call", "phase": "begin", "call": "OpenDoc6", "sequence": 9}])
            connection = Mock()
            def poll(timeout):
                now[0] += 200
                return now[0] <= 400
            connection.poll.side_effect = poll
            connection.recv.side_effect = lambda: next(events)
            process = Mock()
            process.is_alive.return_value = True
            record = {"events": [], "cleanup_errors": []}
            if earlier:
                record["error"] = {"type": "FirstFailure"}
            self.assertFalse(probe.monitor(process, connection, record, Mock(), request_timeout=600, startup_timeout=300, clock=lambda: now[0]))
            if earlier:
                self.assertEqual(record["error"]["type"], "FirstFailure")
                self.assertEqual(record["cleanup_errors"][0]["call"], "OpenDoc6")
            else:
                self.assertEqual(record["error"]["type"], "NativeCallTimeout")
                self.assertEqual(record["error"]["call"], "OpenDoc6")
            process.terminate.assert_not_called()

    def test_cleanup_only_terminates_acquired_host_and_own_child(self):
        process = Mock(pid=44)
        process.is_alive.side_effect = [True, False]
        record = {"host": {"process_id": 123}, "cleanup_errors": []}
        with patch.object(probe.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as command:
            probe.stop_owned_worker(process, record)
        self.assertEqual(command.call_args.args[0], ["taskkill", "/F", "/PID", "123"])
        process.terminate.assert_called_once()
        self.assertEqual(record["cleanup_errors"], [])

    def test_unknown_host_is_never_name_killed(self):
        process = Mock(pid=44)
        process.is_alive.side_effect = [True, False]
        record = {"cleanup_errors": []}
        with patch.object(probe.subprocess, "run") as command:
            probe.stop_owned_worker(process, record)
        command.assert_not_called()
        process.terminate.assert_called_once()
        self.assertEqual(record["cleanup_errors"], [{"type": "HostOwnershipNotEstablished"}])

    def test_host_cleanup_tool_failure_still_terminates_own_child(self):
        process = Mock(pid=44)
        process.is_alive.side_effect = [True, False]
        record = {"host": {"process_id": 123}, "cleanup_errors": [], "error": {"type": "FirstFailure"}}
        with patch.object(probe.subprocess, "run", side_effect=OSError("tool unavailable")):
            probe.stop_owned_worker(process, record)
        process.terminate.assert_called_once()
        self.assertEqual(record["error"], {"type": "FirstFailure"})
        self.assertEqual(record["cleanup_errors"][0]["stage"], "owned-host-cleanup")


class TimeoutBacktraceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "system32").mkdir()
        (self.root / "system32/winedbg.exe").write_bytes(b"bundled debugger")
        self.environment = patch.dict(probe.os.environ, {"SystemRoot": str(self.root), "WINEPREFIX": "private-ci"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.record = {"success": False, "host": {"process_id": 123, "owned_by_probe": True,
                                                  "owned_by_daemon": False},
                       "error": {"type": "NativeCallTimeout", "call": "OpenDoc6", "sequence": 8}}

    def capture(self, content=b'probe-backtrace-begin\nBacktrace:\n=>0 0x00001234 in native\nprobe-backtrace-end\n', error=None):
        def command(arguments, **kwargs):
            self.assertEqual(arguments[-1], "123")
            self.assertEqual(arguments[0], str(self.root / "system32/winedbg.exe"))
            self.assertEqual(arguments[1], "--command")
            commands = arguments[2].splitlines()
            self.assertEqual([c for c in commands if c.startswith("bt ")], ["bt 16", "bt 32"])
            self.assertNotIn("bt all", commands)
            self.assertEqual(commands[-1], "detach")
            self.assertNotIn("minidump", arguments[2])
            self.assertEqual(kwargs["timeout"], 30)
            self.assertEqual(kwargs["env"]["WINEDEBUG"], "-all")
            self.assertEqual(kwargs["env"]["_NT_SYMBOL_PATH"], "")
            kwargs["stdout"].write(content)
            if error:
                raise error
            return SimpleNamespace(returncode=0)
        with patch.object(probe, "native_pids", return_value=[123]), patch.object(probe, "owned_threads", return_value=[16, 32]), patch.object(probe.subprocess, "run", side_effect=command) as call:
            probe.timeout_backtrace(self.record, self.root)
        return call

    def test_only_owned_thread_stacks_after_failed_deadline_and_failure_is_preserved(self):
        self.capture().assert_called_once()
        self.assertTrue(self.record["timeout_backtrace"]["success"])
        self.assertEqual(self.record["timeout_backtrace"]["frame_lines"], 1)
        self.assertEqual(self.record["error"]["sequence"], 8)
        self.assertFalse(self.record["success"])
        self.assertTrue((self.root / "timeout-backtrace.log").is_file())

    def test_tool_timeout_keeps_partial_text_and_first_business_error(self):
        self.capture(content=b"partial text", error=subprocess.TimeoutExpired("winedbg", 30))
        self.assertEqual((self.root / "timeout-backtrace.log").read_bytes(), b"partial text")
        self.assertFalse(self.record["timeout_backtrace"]["success"])
        self.assertEqual(self.record["timeout_backtrace"]["diagnostic_error"], "TimeoutExpired")
        self.assertEqual(self.record["error"]["type"], "NativeCallTimeout")

    def test_output_is_bounded_and_truncation_never_proves_capture(self):
        self.capture(content=b"x" * (probe.BACKTRACE_MAX_BYTES + 2))
        self.assertEqual((self.root / "timeout-backtrace.log").stat().st_size, probe.BACKTRACE_MAX_BYTES)
        self.assertTrue(self.record["timeout_backtrace"]["truncated"])
        self.assertFalse(self.record["timeout_backtrace"]["success"])

    def test_exit_zero_without_real_frames_is_not_success(self):
        self.capture(content=b"probe-backtrace-end\nBacktrace:\n")
        self.assertFalse(self.record["timeout_backtrace"]["success"])

    def test_non_owned_or_unconfirmed_host_never_runs_debugger(self):
        for field, value in (("owned_by_probe", False), ("owned_by_daemon", True), ("process_id", "123")):
            with self.subTest(field=field), patch.dict(self.record["host"], {field: value}), patch.object(probe.subprocess, "run") as command:
                probe.timeout_backtrace(self.record, self.root)
                command.assert_not_called()
                self.assertFalse(self.record["timeout_backtrace"]["success"])

    def test_exited_host_is_not_replaced_with_a_different_target(self):
        with patch.object(probe, "native_pids", return_value=[999]), patch.object(probe.subprocess, "run") as command:
            probe.timeout_backtrace(self.record, self.root)
        command.assert_not_called()

    def test_unknown_thread_snapshot_does_not_fallback_to_all(self):
        with patch.object(probe, "native_pids", return_value=[123]), patch.object(probe, "owned_threads", side_effect=OSError("unavailable")), patch.object(probe.subprocess, "run") as command:
            probe.timeout_backtrace(self.record, self.root)
        command.assert_not_called()
        self.assertEqual(self.record["timeout_backtrace"]["diagnostic_error"], "OSError")

    def test_checkpoint_of_failed_call_precedes_debugger(self):
        checkpoint = Mock()
        def debugger(record, output):
            checkpoint.assert_called_once()
            self.assertFalse(record["success"])
        with patch.object(probe, "timeout_backtrace", side_effect=debugger) as capture:
            probe.diagnose_timeout(SimpleNamespace(timeout_backtrace=True, output_dir=self.root), self.record, checkpoint)
        capture.assert_called_once()
        self.assertEqual(checkpoint.call_count, 2)

    def test_no_capture_before_timeout_for_other_failure_or_when_not_requested(self):
        for enabled, error in ((False, self.record["error"]), (True, {"type": "OtherFailure"}),
                               (True, {"type": "NativeCallTimeout", "call": "ExitApp"}), (True, {})):
            with self.subTest(enabled=enabled, error=error), patch.object(probe, "timeout_backtrace") as capture:
                probe.diagnose_timeout(SimpleNamespace(timeout_backtrace=enabled), {"error": error}, Mock())
                capture.assert_not_called()

    def test_thread_snapshot_filters_pid_and_always_closes_handle(self):
        import ctypes
        kernel = SimpleNamespace(CreateToolhelp32Snapshot=Mock(return_value=77), Thread32First=Mock(),
                                 Thread32Next=Mock(), CloseHandle=Mock())
        entries = iter([(123, 32), (999, 1), (123, 16)])
        def next_thread(snapshot, reference):
            self.assertEqual(snapshot, 77)
            item = next(entries, None)
            if item is None:
                return False
            reference._obj.th32OwnerProcessID, reference._obj.th32ThreadID = item
            return True
        kernel.Thread32First.side_effect = kernel.Thread32Next.side_effect = next_thread
        with patch.object(ctypes, "WinDLL", return_value=kernel, create=True), patch.object(ctypes, "get_last_error", return_value=18, create=True):
            self.assertEqual(probe.owned_threads(123), [16, 32])
        kernel.CloseHandle.assert_called_once_with(77)

    def test_partial_thread_snapshot_fails_and_closes_handle(self):
        import ctypes
        kernel = SimpleNamespace(CreateToolhelp32Snapshot=Mock(return_value=77), Thread32First=Mock(return_value=True),
                                 Thread32Next=Mock(return_value=False), CloseHandle=Mock())
        with patch.object(ctypes, "WinDLL", return_value=kernel, create=True), patch.object(ctypes, "get_last_error", return_value=5, create=True):
            with self.assertRaisesRegex(OSError, "enumeration failed"):
                probe.owned_threads(123)
        kernel.CloseHandle.assert_called_once_with(77)

    def test_invalid_snapshot_handle_is_not_enumerated(self):
        import ctypes
        kernel = SimpleNamespace(CreateToolhelp32Snapshot=Mock(return_value=ctypes.c_void_p(-1).value),
                                 Thread32First=Mock(), Thread32Next=Mock(), CloseHandle=Mock())
        with patch.object(ctypes, "WinDLL", return_value=kernel, create=True):
            with self.assertRaisesRegex(OSError, "snapshot unavailable"):
                probe.owned_threads(123)
        kernel.Thread32First.assert_not_called()
        kernel.CloseHandle.assert_not_called()

    def test_requested_missing_debugger_fails_before_any_cad_host(self):
        (self.root / "system32/winedbg.exe").unlink()
        with patch.object(probe.sys, "platform", "win32"), patch.dict(probe.os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(probe, "native_pids") as inventory:
            with self.assertRaisesRegex(RuntimeError, "uninstrumented repeat"):
                probe.run(SimpleNamespace(timeout_backtrace=True))
        inventory.assert_not_called()

    def test_windows_without_wine_cannot_opt_into_wine_debugger(self):
        with patch.object(probe.sys, "platform", "win32"), patch.dict(probe.os.environ, {"GITHUB_ACTIONS": "true", "WINEPREFIX": ""}):
            with self.assertRaisesRegex(RuntimeError, "Wine-only"):
                probe.run(SimpleNamespace(timeout_backtrace=True))


if __name__ == "__main__":
    unittest.main()
