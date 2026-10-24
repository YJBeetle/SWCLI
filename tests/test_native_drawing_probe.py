"""Offline native-control safety checks, not SOLIDWORKS runtime acceptance."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
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


if __name__ == "__main__":
    unittest.main()
