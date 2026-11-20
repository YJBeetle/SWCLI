"""Portable fault injection through actual line-font handler and worker, never COM."""
from types import SimpleNamespace
import unittest
from unittest import mock
import test_document_line_font as fixtures
from swcli.daemon import server
from swcli.daemon import operations
from swcli.result_schemas import validate_operation_result


class LineFontPostconditions(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.LineFontTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.fx = self.case.fx
        self.fx.app.CommandInProgress = False
        self.fx.app.RevisionNumber = "33.5.0"
        self.fx.app.GetProcessID = lambda: 1234

    def worker(self):
        pythoncom, client, responses, lifecycle = mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
        request = dict(request_id="line-font-fault", operation="document.line-font-set",
            parameters=dict(field="visible_edges.style", value=1, expected_options=self.case.before),
            session_id="writer", document_id=self.fx.entry.document_id, expected_update_stamp=7,
            lease_id=self.fx.lease["lease_id"])
        with mock.patch.dict("sys.modules", {"pythoncom": pythoncom,
                "win32com": mock.Mock(client=client), "win32com.client": client}), \
             mock.patch.object(server, "acquire_resident_app", return_value=(self.fx.app, True)), \
             mock.patch.object(server, "wait_windows_host_ready", return_value=0), \
             mock.patch.object(server, "DocumentRegistry", return_value=self.fx.documents), \
             mock.patch.object(server, "_describe_app", return_value=dict(process_id=1234)), \
             mock.patch.object(server, "_wait_for_worker_request", side_effect=[request, None]):
            # execute_operation, native_api_sequence, adapter, handler, result
            # validation and transport error construction are all production code.
            server._worker_main(mock.Mock(), responses, lifecycle, False, 120, False)
        pythoncom.CoUninitialize.assert_called_once()
        self.assertEqual(responses.put.call_count, 1)
        self.assertFalse(self.fx.app.CommandInProgress)
        self.assertFalse(any(call.args[0].get("event") == "host-disconnected" for call in lifecycle.put.call_args_list))
        return responses.put.call_args.args[0]

    def test_worker_preserves_receipt_and_first_error_when_final_describe_fails(self):
        for native_failure in (False, True):
            with self.subTest(native_failure=native_failure):
                self.setUp()
                def setter(pref, option, value):
                    self.fx.native[pref] = value
                    if native_failure:
                        raise ValueError("first native failure")
                    return True
                self.fx.extension.SetUserPreferenceInteger.side_effect = setter
                describe = self.fx.documents.describe
                def observe(*args, **kwargs):
                    if self.fx.extension.SetUserPreferenceInteger.call_count:
                        raise RuntimeError("post-set descriptor failed")
                    return describe(*args, **kwargs)
                with mock.patch.object(self.fx.documents, "describe", side_effect=observe) as observed:
                    response = self.worker()
                self.assertFalse(response["success"])
                result = response["result"]
                self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
                self.assertEqual(result["finalization_error"], dict(type="RuntimeError", message="post-set descriptor failed"))
                self.assertEqual(result["session_id"], "writer")
                validate_operation_result("document.line-font-set", result)
                self.transport_receipts(response)
                self.fx.extension.SetUserPreferenceInteger.assert_called_once_with(101, 0, 1)
                self.assertEqual(observed.call_count, 2)  # initial CAS stamp + one final descriptor
                if native_failure:
                    self.assertEqual(result["error"], dict(type="ValueError", message="first native failure"))
                    self.assertEqual(response["error"]["code"], "ValueError")
                    self.fx.document.SetSaveFlag.assert_not_called()
                else:
                    self.assertTrue(result["changed"])
                    self.assertIn("finalization failed", result["error"]["message"])

    def transport_receipts(self, response):
        from swcli.sdk import Client
        from swcli.mcp import DaemonBridge
        args = dict(field="visible_edges.style", value=1, expected_options=self.case.before,
                    document_id=self.fx.entry.document_id, expected_update_stamp=7,
                    lease_id=self.fx.lease["lease_id"], request_id="line-font-fault")
        with mock.patch("swcli.sdk.client.call_daemon", return_value=response) as transport:
            received = Client(session_id="writer").document.line_font_set(**args)
        transport.assert_called_once()
        self.assertFalse(received.success)
        self.assertEqual(received.result["mutation"], response["result"]["mutation"])
        self.assertEqual(received.result["error"], response["result"]["error"])
        self.assertEqual(received.result["finalization_error"], response["result"]["finalization_error"])
        arguments = dict(operation="document.line-font-set", parameters={k:args[k] for k in ("field", "value", "expected_options")},
                         **{k:args[k] for k in ("document_id", "expected_update_stamp", "lease_id", "request_id")})
        with mock.patch("swcli.mcp.DaemonManager"), mock.patch("swcli.mcp.call_daemon", return_value=response) as transport:
            received = DaemonBridge(session_id="writer").call("execute", arguments)
        transport.assert_called_once()
        self.assertFalse(received["success"])
        self.assertEqual(received["result"], response["result"])

    def test_handler_retains_adapter_receipt_on_success_and_existing_failure(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                receipt = dict(ok=not failed, action="document.line-font-set",
                               mutation=dict(attempted=True, may_have_changed=True))
                if failed:
                    receipt["error"] = dict(type="NativeFirst", message="original error")
                context = SimpleNamespace(app=object(), entry=SimpleNamespace(document=object()), session_id="writer",
                    documents=SimpleNamespace(describe=mock.Mock(side_effect=RuntimeError("descriptor failed"))))
                with mock.patch.object(operations, "set_document_line_font_windows", return_value=receipt) as setter:
                    result = operations.document_line_font_set(context, {})
                setter.assert_called_once()
                context.documents.describe.assert_called_once()
                self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
                self.assertFalse(result["ok"])
                if failed:
                    self.assertEqual(result["error"], dict(type="NativeFirst", message="original error"))
                self.assertEqual(result["finalization_error"]["message"], "descriptor failed")

    def test_worker_rejects_same_object_foreground_drift_without_rollback(self):
        for member, value in (("GetUpdateStamp", 99999), ("GetSaveFlag", True),
                              ("GetTitle", "Peer changed"), ("GetPathName", r"C:\peer-changed.SLDPRT")):
            with self.subTest(member=member):
                self.setUp()
                peer = self.fx.foreground
                apply = self.fx.apply
                def setter(pref, option, native):
                    returned = apply(pref, option, native)
                    setattr(peer, member, lambda: value)
                    return returned
                self.fx.extension.SetUserPreferenceInteger.side_effect = setter
                response = self.worker()
                self.assertFalse(response["success"], response)
                result = response["result"]
                self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
                self.assertIn("foreground", result["error"]["message"])
                self.assertIs(self.fx.app.ActiveDoc, peer)
                self.assertEqual(getattr(peer, member)(), value)  # no restoration
                self.fx.extension.SetUserPreferenceInteger.assert_called_once_with(101, 0, 1)
                self.fx.document.SetSaveFlag.assert_not_called()
                validate_operation_result("document.line-font-set", result)

    def test_pre_set_foreground_drift_is_refused_without_attempt(self):
        def getter(pref, option):
            self.fx.foreground.GetSaveFlag = lambda: True
            return self.fx.native[pref]
        self.fx.extension.GetUserPreferenceInteger.side_effect = getter
        result = self.case.edit(_internal_calibration=True)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["mutation"], dict(attempted=False, may_have_changed=False))
        self.fx.assert_no_setters()

    def test_foreground_access_configuration_and_sketch_remain_protected(self):
        for drift in ("access", "configuration", "sketch"):
            with self.subTest(drift=drift):
                self.setUp()
                apply = self.fx.apply
                def setter(pref, option, native):
                    returned = apply(pref, option, native)
                    if drift == "access":
                        self.fx.foreground.IsOpenedReadOnly = lambda: True
                    elif drift == "configuration":
                        self.fx.foreground.ConfigurationManager = SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Other"))
                    else:
                        self.fx.foreground.SketchManager.ActiveSketch = object()
                    return returned
                self.fx.extension.SetUserPreferenceInteger.side_effect = setter
                result = self.case.edit(_internal_calibration=True)
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.fx.extension.SetUserPreferenceInteger.assert_called_once()
                self.fx.document.SetSaveFlag.assert_not_called()

    def test_target_identity_or_document_close_is_partial_failure(self):
        for drift in ("title", "path", "closed"):
            with self.subTest(drift=drift):
                self.setUp()
                apply = self.fx.apply
                def setter(pref, option, native):
                    returned = apply(pref, option, native)
                    if drift == "title":
                        self.fx.document.GetTitle = lambda: "Renamed"
                    elif drift == "path":
                        self.fx.document.GetPathName = lambda: r"C:\renamed.SLDDRW"
                    else:
                        self.fx.app.GetDocuments = lambda: (self.fx.foreground,)
                    return returned
                self.fx.extension.SetUserPreferenceInteger.side_effect = setter
                result = self.case.edit(_internal_calibration=True)
                self.assertFalse(result["ok"], result)
                self.assertTrue(result["mutation"]["may_have_changed"])
                self.fx.extension.SetUserPreferenceInteger.assert_called_once()
                self.fx.document.SetSaveFlag.assert_not_called()

    def test_foreground_target_is_allowed_to_become_dirty(self):
        self.fx.app.ActiveDoc = self.fx.document
        result = self.case.edit(_internal_calibration=True)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["changed"])
        self.fx.extension.SetUserPreferenceInteger.assert_called_once()
