import io
import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from swcli.daemon import server
from swcli.hosts.native_sequence import NativeCommandRestoreFailed, native_api_sequence
from swcli.hosts.native_trace import trace_native_request


class NativeSequenceTests(unittest.TestCase):
    class App:
        def __init__(self, initial=False):
            self.value = initial
            self.writes = []

        @property
        def CommandInProgress(self):
            return self.value

        @CommandInProgress.setter
        def CommandInProgress(self, value):
            self.writes.append(value)
            self.value = value

    def test_owned_sequence_restores_false(self):
        app = self.App()
        with native_api_sequence(app, enabled=True):
            self.assertTrue(app.CommandInProgress)
        self.assertFalse(app.CommandInProgress)
        self.assertEqual([True, False], app.writes)

    def test_existing_true_is_preserved_without_writes(self):
        app = self.App(True)
        with native_api_sequence(app, enabled=True):
            self.assertTrue(app.CommandInProgress)
        self.assertTrue(app.CommandInProgress)
        self.assertEqual([], app.writes)

    def test_shared_host_does_not_even_read_property(self):
        with native_api_sequence(object(), enabled=False):
            pass

    def test_failed_read_does_not_dispatch_or_write(self):
        failure = RuntimeError("read failed")

        class App(self.App):
            @NativeSequenceTests.App.CommandInProgress.getter
            def CommandInProgress(self):
                raise failure

        app = App()
        with self.assertRaises(RuntimeError) as caught:
            with native_api_sequence(app, enabled=True):
                self.fail("operation must not run")
        self.assertIs(failure, caught.exception)
        self.assertEqual([], app.writes)

    def test_operation_error_identity_survives_restoration(self):
        app, failure = self.App(), RuntimeError("native failure")
        with self.assertRaises(RuntimeError) as caught:
            with native_api_sequence(app, enabled=True):
                raise failure
        self.assertIs(failure, caught.exception)
        self.assertFalse(app.CommandInProgress)

    def test_base_exception_also_restores(self):
        app = self.App()
        with self.assertRaises(KeyboardInterrupt):
            with native_api_sequence(app, enabled=True):
                raise KeyboardInterrupt()
        self.assertFalse(app.CommandInProgress)

    def test_nested_scope_does_not_clear_outer_state(self):
        app = self.App()
        with native_api_sequence(app, enabled=True):
            with native_api_sequence(app, enabled=True):
                self.assertTrue(app.CommandInProgress)
            self.assertTrue(app.CommandInProgress)
        self.assertEqual([True, False], app.writes)

    def test_failed_enter_still_restores_before_propagating(self):
        failure = RuntimeError("enter failed after change")

        class App(self.App):
            @NativeSequenceTests.App.CommandInProgress.setter
            def CommandInProgress(self, value):
                self.value = value
                if value:
                    raise failure

        app = App()
        with self.assertRaises(RuntimeError) as caught:
            with native_api_sequence(app, enabled=True):
                self.fail("operation must not run")
        self.assertIs(failure, caught.exception)
        self.assertFalse(app.CommandInProgress)

    def test_restore_failure_retains_both_failures(self):
        restore_error, operation_error = RuntimeError("restore"), ValueError("operation")

        class App(self.App):
            @NativeSequenceTests.App.CommandInProgress.setter
            def CommandInProgress(self, value):
                if not value:
                    raise restore_error
                self.value = value

        with self.assertRaises(NativeCommandRestoreFailed) as caught:
            with native_api_sequence(App(), enabled=True):
                raise operation_error
        self.assertIs(operation_error, caught.exception.operation_error)
        self.assertIs(restore_error, caught.exception.restore_error)
        self.assertIs(restore_error, caught.exception.__cause__)

    def test_restore_failure_after_success_is_not_silent(self):
        class App(self.App):
            @NativeSequenceTests.App.CommandInProgress.setter
            def CommandInProgress(self, value):
                if not value:
                    raise RuntimeError("restore failed")
                self.value = value

        with self.assertRaises(NativeCommandRestoreFailed) as caught:
            with native_api_sequence(App(), enabled=True):
                pass
        self.assertIsNone(caught.exception.operation_error)

    def test_ignored_enter_does_not_dispatch_operation(self):
        class App(self.App):
            @NativeSequenceTests.App.CommandInProgress.setter
            def CommandInProgress(self, value):
                pass

        with self.assertRaisesRegex(RuntimeError, "did not enter"):
            with native_api_sequence(App(), enabled=True):
                self.fail("operation must not run")

    def test_ignored_restore_is_detected(self):
        class App(self.App):
            @NativeSequenceTests.App.CommandInProgress.setter
            def CommandInProgress(self, value):
                if value:
                    self.value = value

        with self.assertRaises(NativeCommandRestoreFailed):
            with native_api_sequence(App(), enabled=True):
                pass

    def test_opt_in_trace_covers_enter_and_restore(self):
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"SWCLI_TRACE_NATIVE_CALLS": "1"}), \
                mock.patch("swcli.hosts.native_trace.sys.stderr", output):
            with trace_native_request("request", "document.list"):
                with native_api_sequence(self.App(), enabled=True):
                    pass
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        calls = [(e["call"], e["phase"]) for e in events if e["stage"] == "api-sequence"]
        self.assertEqual([
            ("SldWorks.CommandInProgress.enter", "begin"),
            ("SldWorks.CommandInProgress.enter", "end"),
            ("SldWorks.CommandInProgress.restore", "begin"),
            ("SldWorks.CommandInProgress.restore", "end"),
        ], calls)

    def run_worker(self, app, owned, execute, requests):
        pythoncom, com_client = mock.Mock(), mock.Mock()
        responses, lifecycle = mock.Mock(), mock.Mock()
        with mock.patch.dict("sys.modules", {
            "pythoncom": pythoncom, "win32com": mock.Mock(client=com_client),
            "win32com.client": com_client,
        }), mock.patch.object(server, "acquire_resident_app", return_value=(app, owned)), \
                mock.patch.object(server, "wait_windows_host_ready", return_value=0), \
                mock.patch.object(server, "DocumentRegistry"), \
                mock.patch.object(server, "_describe_app", return_value={"process_id": 1234}), \
                mock.patch.object(server, "_wait_for_worker_request", side_effect=requests) as wait, \
                mock.patch.object(server, "execute_operation", side_effect=execute), \
                mock.patch.object(server, "validate_operation_result"):
            server._worker_main(mock.Mock(), responses, lifecycle, True, 120, not owned)
        pythoncom.CoUninitialize.assert_called_once()
        return responses, lifecycle, wait

    def test_worker_restores_before_next_request_and_shutdown(self):
        exited = []
        app = SimpleNamespace(CommandInProgress=False, GetProcessID=lambda: 1234,
                              RevisionNumber="33.5.0", ActiveDoc=None,
                              ExitApp=lambda: exited.append(app.CommandInProgress))
        request = {"request_id": "one", "operation": "document.list", "parameters": {}}
        shutdown = {**request, "request_id": "shutdown", "operation": "__daemon.shutdown__"}

        def execute(*args, **kwargs):
            self.assertTrue(app.CommandInProgress)
            return {"ok": True}

        responses, lifecycle, wait = self.run_worker(app, True, execute, [request, shutdown])
        self.assertFalse(app.CommandInProgress)
        self.assertTrue(responses.put.call_args.args[0]["success"])
        self.assertEqual([False], exited)
        self.assertEqual(2, wait.call_count)

    def test_worker_does_not_change_shared_host(self):
        app = SimpleNamespace(GetProcessID=lambda: 1234, RevisionNumber="33.5.0")
        request = {"request_id": "shared", "operation": "document.list", "parameters": {}}
        responses, lifecycle, wait = self.run_worker(app, False, lambda *a, **k: {"ok": True}, [request, None])
        self.assertFalse(hasattr(app, "CommandInProgress"))
        self.assertTrue(responses.put.call_args.args[0]["success"])

    def test_structured_operation_failure_restores_and_allows_next_request(self):
        app = SimpleNamespace(CommandInProgress=False, GetProcessID=lambda: 1234,
                              RevisionNumber="33.5.0", ActiveDoc=object())
        first = {"request_id": "first", "operation": "document.list", "parameters": {}}
        second = {**first, "request_id": "second"}
        results = iter([
            {"ok": False, "error": {"type": "ExpectedNativeFailure", "message": "failed"}},
            {"ok": True},
        ])

        def execute(*args, **kwargs):
            self.assertTrue(app.CommandInProgress)
            return next(results)

        responses, lifecycle, wait = self.run_worker(app, True, execute, [first, second, None])
        replies = [call.args[0] for call in responses.put.call_args_list]
        self.assertEqual("ExpectedNativeFailure", replies[0]["error"]["code"])
        self.assertTrue(replies[1]["success"])
        self.assertFalse(app.CommandInProgress)
        self.assertFalse(any(call.args[0].get("event") == "host-disconnected"
                             for call in lifecycle.put.call_args_list))

    def test_worker_restore_failure_ends_dispatch_and_reports_recovery(self):
        app = SimpleNamespace(CommandInProgress=False, GetProcessID=lambda: 1234,
                              RevisionNumber="33.5.0", ActiveDoc=object())
        request = {"request_id": "failed", "operation": "document.list", "parameters": {}}
        failure = NativeCommandRestoreFailed(RuntimeError("restore"), None)
        responses, lifecycle, wait = self.run_worker(
            app, True, mock.Mock(side_effect=failure), [request, request, None]
        )
        self.assertEqual(1, wait.call_count)
        response = responses.put.call_args.args[0]
        self.assertFalse(response["success"])
        self.assertEqual("NativeCommandRestoreFailed", response["error"]["code"])
        event = lifecycle.put.call_args.args[0]
        self.assertEqual("host-disconnected", event["event"])
        self.assertEqual(response["error"], event["error"])

    @mock.patch("swcli.daemon.server.subprocess.run")
    def test_restore_failure_cleans_owned_host_after_worker_exit_and_blocks_reuse(self, run):
        manager = object.__new__(server.WorkerManager)
        manager._lock = server.threading.Lock()
        manager._process = mock.Mock()
        # Alive before dispatch, exited after returning the terminal error.
        manager._process.is_alive.side_effect = [True, True, False, False]
        manager._request_queue = mock.Mock()
        manager._response_queue = mock.Mock()
        manager._lifecycle_queue = None
        manager._recovery_required = None
        manager._request_cache = server.OrderedDict()
        manager._request_cache_bytes = 0
        manager.host = {"process_id": 1234, "owned_by_daemon": True}
        manager._start_worker = mock.Mock()
        manager._response_queue.get.return_value = server._error_response(
            "failed", "NativeCommandRestoreFailed", "restore failed"
        )
        failed = manager.call({"request_id": "failed", "timeout_ms": 1000})
        blocked = manager.call({"request_id": "next", "timeout_ms": 1000})
        self.assertEqual("NativeCommandRestoreFailed", failed["error"]["code"])
        self.assertEqual(failed["error"], blocked["error"])
        self.assertEqual({}, manager.host)
        self.assertIsNone(manager._process)
        manager._start_worker.assert_not_called()
        run.assert_called_once()
        self.assertEqual(["taskkill", "/PID", "1234", "/T", "/F"], run.call_args.args[0])

    @mock.patch("swcli.daemon.server.subprocess.run")
    def test_forced_host_cleanup_never_kills_shared_instance(self, run):
        manager = object.__new__(server.WorkerManager)
        manager._process = mock.Mock()
        manager._process.is_alive.return_value = False
        manager.host = {"process_id": 1234, "owned_by_daemon": False}
        manager._terminate_worker(force_owned_host=True)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
