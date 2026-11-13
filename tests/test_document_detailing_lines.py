"""Portable candidate contracts and real guard paths; no native acceptance."""

from contextlib import redirect_stderr
from collections import Counter, namedtuple
from copy import deepcopy
from io import StringIO
import json
from types import SimpleNamespace
import unittest
from unittest import mock

from swcli.cli import build_parser, _typed_operation
from swcli.daemon import operations, server
from swcli.daemon.documents import DocumentLeaseConflict
from swcli.daemon.operations import DocumentUpdateConflict, execute_operation
from swcli.document_detailing import DETAILING_FIELDS
from swcli.document_detailing_lines import DETAILING_LINE_FIELDS, DETAILING_LINE_SNAPSHOT_FIELDS
from swcli.hosts import windows_document_detailing as legacy
from swcli.hosts import windows_document_detailing_lines as adapter
from swcli.hosts.native_trace import trace_native_request
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.result_schemas import OperationResultInvalid, validate_operation_result
from swcli.sdk import Client, RemoteError
from swcli.mcp import DaemonBridge
from tests import test_document_detailing as legacy_fixtures

READ, SET = "document.detailing-line-options", "document.detailing-line-option-set"


class DetailingLineTests(unittest.TestCase):
    def setUp(self):
        self.fx = legacy_fixtures.DetailingTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.fields = tuple(DETAILING_LINE_FIELDS)
        # Arbitrary portable IDs; never substitute these for official swconst.
        self.fx.constants.update(dict(zip(DETAILING_LINE_FIELDS.values(), (903, 904))))
        self.fx.native.update({903: False, 904: True})

    def options(self):
        return {field: self.fx.native[self.fx.constants[symbol]] for field, symbol in DETAILING_LINE_SNAPSHOT_FIELDS.items()}

    def parameters(self, *, field=None, value=True, expected=None):
        return dict(field=field or self.fields[0], value=value,
                    expected_options=self.options() if expected is None else expected)

    def call(self, operation=READ, parameters=None, **context):
        return execute_operation(self.fx.app, operation, parameters or {}, documents=self.fx.registry,
            session_id=context.pop("session_id", "writer"), document_id=self.fx.entry.document_id,
            expected_update_stamp=context.pop("expected_update_stamp", 7),
            lease_id=context.pop("lease_id", self.fx.lease["lease_id"] if operation == SET else None), **context)

    def proof(self):
        # A portable fake, never persisted as native proof or exposed on wire.
        return mock.patch.object(adapter, "CALIBRATED_LINE_REVISIONS", frozenset({"test-revision"}))

    def test_read_has_four_values_but_legacy_read_contract_remains_two(self):
        result = self.call()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["write_enabled"])
        self.assertEqual(result["options"], self.options())
        self.assertEqual(self.fx.extension.GetUserPreferenceToggle.call_count, 4)
        validate_operation_result(READ, result)
        old = self.fx.call()
        self.assertEqual(set(old["options"]), set(DETAILING_FIELDS))
        self.assertNotIn("write_enabled", old)
        validate_operation_result("document.detailing-options", old)
        self.fx.assert_untouched()

    def test_every_unproven_set_including_noop_is_closed_without_native_preferences(self):
        self.fx.app.RevisionNumber = lambda: "33.5.0"
        with mock.patch.object(legacy, "CALIBRATED_REVISIONS", frozenset({"33.5.0"})), \
                mock.patch.dict("os.environ", {"SWCLI_DETAILING_LINE_WRITES": "1"}):
            for value in (False, True):
                result = self.call(SET, self.parameters(value=value))
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["write_enabled"])
                self.assertEqual(result["mutation"], dict(attempted=False, may_have_changed=False))
                validate_operation_result(SET, result)
        self.fx.extension.GetUserPreferenceToggle.assert_not_called()
        self.fx.assert_untouched()

    def test_fake_proven_both_values_noop_and_legacy_guards_preserved(self):
        original = {key: self.options()[key] for key in DETAILING_FIELDS}
        with self.proof():
            for field in self.fields:
                for value in (not self.options()[field], self.options()[field]):
                    result = self.call(SET, self.parameters(field=field, value=value))
                    self.assertTrue(result["ok"], result)
                    self.assertTrue(result["write_enabled"])
                    self.assertTrue(result["changed"])
                    self.assertFalse(result["document"]["active"])
                    self.assertFalse(result["document"]["current"])
                    self.assertEqual({key: result["options"][key] for key in DETAILING_FIELDS}, original)
                    validate_operation_result(SET, result)
                    noop = self.call(SET, self.parameters(field=field, value=value))
                    self.assertTrue(noop["ok"], noop)
                    self.assertFalse(noop["changed"])
                    self.assertEqual(noop["mutation"], dict(attempted=False, may_have_changed=False))
                    validate_operation_result(SET, noop)
        self.assertEqual(self.fx.extension.SetUserPreferenceToggle.call_count, 4)
        self.fx.document.SetSaveFlag.assert_called_once()
        self.fx.app.ActivateDoc3.assert_not_called()

    def test_cas_detects_stale_legacy_guard_and_new_neighbor_without_stamp_change(self):
        for field in DETAILING_LINE_SNAPSHOT_FIELDS:
            with self.subTest(field=field), self.proof():
                expected = self.options()
                code = self.fx.constants[DETAILING_LINE_SNAPSHOT_FIELDS[field]]
                self.fx.native[code] = not self.fx.native[code]
                result = self.call(SET, self.parameters(expected=expected))
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["mutation"]["attempted"])
                self.fx.native[code] = not self.fx.native[code]
                validate_operation_result(SET, result)
        self.fx.assert_untouched()

    def test_lease_stamp_and_complete_four_boolean_schema_precede_dispatch(self):
        with self.assertRaises(DocumentLeaseConflict):
            self.call(SET, self.parameters(), session_id="other")
        with self.assertRaises(DocumentUpdateConflict):
            self.call(SET, self.parameters(), expected_update_stamp=6)
        context = dict(document_id=self.fx.entry.document_id, expected_update_stamp=7, lease_id=self.fx.lease["lease_id"])
        for key in context:
            with self.assertRaises(ValueError):
                validate_operation_request(SET, self.parameters(), **{**context, key: None})
        bad_snapshots = ({}, {key: self.options()[key] for key in DETAILING_LINE_FIELDS},
                         {key: self.options()[key] for key in DETAILING_FIELDS},
                         {**self.options(), self.fields[0]: 0}, {**self.options(), "extra": False})
        for expected in bad_snapshots:
            with self.assertRaises(ValueError):
                validate_operation_request(SET, self.parameters(expected=expected), **context)
        for field in DETAILING_FIELDS:
            with self.assertRaises(ValueError):
                validate_operation_request(SET, self.parameters(field=field), **context)
        for flag in ("allow_unverified", "calibration", "profile"):
            with self.assertRaises(ValueError):
                validate_operation_request(SET, {**self.parameters(), flag: True}, **context)
        self.fx.assert_untouched()

    def test_readonly_and_drawing_modes_block_fake_proven_setter(self):
        defects = ((self.fx.document, "IsOpenedReadOnly", lambda: True),
                   (self.fx.document, "IsOpenedViewOnly", lambda: True),
                   (self.fx.document, "GetType", lambda: 2),
                   (self.fx.document, "GetEditSheet", lambda: False),
                   (self.fx.document, "ActiveDrawingView", object()),
                   (self.fx.document.SketchManager, "ActiveSketch", object()),
                   (self.fx.document.SketchManager, "ActiveSketch", None))
        for target, key, value in defects:
            with self.subTest(key=key), self.proof(), mock.patch.object(target, key, value):
                result = adapter.set_document_detailing_line_option_windows(
                    app=self.fx.app, document=self.fx.document, **self.parameters())
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["mutation"]["attempted"])
                self.fx.assert_untouched()

    def test_unrecognized_revision_or_wine_is_not_enabled_by_other_proof(self):
        with self.proof(), mock.patch.object(legacy, "_native_windows", return_value=False):
            result = self.call(SET, self.parameters())
        self.assertFalse(result["ok"], result)
        with self.proof():
            self.fx.app.RevisionNumber = lambda: "33.5.0"
            result = self.call(SET, self.parameters())
        self.assertFalse(result["ok"], result)
        self.fx.assert_untouched()

    def test_setter_false_or_exception_keeps_partial_receipt_without_retry(self):
        for failure in (False, "raise"):
            self.fx.extension.SetUserPreferenceToggle.reset_mock()
            self.fx.native[903] = False
            def setter(pref, option, value):
                self.fx.native[pref] = value
                if failure == "raise":
                    raise RuntimeError("first native line failure")
                return False
            with self.proof():
                self.fx.extension.SetUserPreferenceToggle.side_effect = setter
                result = self.call(SET, self.parameters())
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
            self.assertTrue(self.fx.native[903])
            self.fx.extension.SetUserPreferenceToggle.assert_called_once()
            self.fx.document.SetSaveFlag.assert_not_called()
            validate_operation_result(SET, result)

    def test_unrequested_old_guard_change_is_a_partial_failure_not_a_rollback(self):
        def setter(pref, option, value):
            self.fx.native[pref] = value
            self.fx.native[901] = not self.fx.native[901]
            return True
        self.fx.extension.SetUserPreferenceToggle.side_effect = setter
        with self.proof():
            result = self.call(SET, self.parameters())
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.fx.extension.SetUserPreferenceToggle.assert_called_once()
        self.fx.document.SetSaveFlag.assert_not_called()

    def test_getter_and_dirty_mark_identity_drift_are_not_repaired(self):
        original = self.fx.extension.GetUserPreferenceToggle.side_effect
        def getter(pref, option):
            self.fx.foreground.GetSaveFlag = lambda: True
            return original(pref, option)
        self.fx.extension.GetUserPreferenceToggle.side_effect = getter
        result = self.call()
        self.assertFalse(result["ok"], result)
        self.fx.assert_untouched()
        self.fx.foreground.GetSaveFlag = lambda: False
        self.fx.extension.GetUserPreferenceToggle.side_effect = original
        def mark():
            self.fx.modified = True
            self.fx.document.GetPathName = lambda: "unexpected.SLDDRW"
        self.fx.document.SetSaveFlag.side_effect = mark
        with self.proof():
            result = self.call(SET, self.parameters())
        self.assertFalse(result["ok"], result)
        self.assertTrue(result["mutation"]["may_have_changed"])
        self.fx.document.SetSaveFlag.assert_called_once()

    def test_descriptor_fault_preserves_first_error_and_actual_mutation(self):
        self.fx.extension.SetUserPreferenceToggle.side_effect = RuntimeError("first native line failure")
        with self.proof(), mock.patch.object(operations, "_with_document", side_effect=RuntimeError("late descriptor failure")):
            result = self.call(SET, self.parameters())
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"]["message"], "first native line failure")
        self.assertEqual(result["error"]["descriptor_error"]["message"], "late descriptor failure")
        self.assertEqual(result["mutation"], dict(attempted=True, may_have_changed=True))
        validate_operation_result(SET, result)

    def test_real_adapter_trace_keeps_flat_complete_native_boundaries(self):
        output = StringIO()
        with self.proof(), mock.patch.dict("os.environ", {"SWCLI_TRACE_NATIVE_CALLS": "1"}), redirect_stderr(output):
            with trace_native_request("portable-line-trace", SET):
                result = self.call(SET, self.parameters())
        self.assertTrue(result["ok"], result)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual((rows[0]["sequence"], rows[-1]["sequence"]), (0, 0))
        calls = rows[1:-1]
        for sequence, (begin, end) in enumerate(zip(calls[::2], calls[1::2]), 1):
            self.assertEqual((begin["sequence"], end["sequence"]), (sequence, sequence))
            self.assertEqual((begin["phase"], end["phase"]), ("begin", "end"))
            self.assertEqual(begin["call"], end["call"])
        names = Counter(row["call"] for row in rows if row["phase"] == "begin")
        self.assertEqual(names["IModelDocExtension.GetUserPreferenceToggle"], 12)
        self.assertEqual(names["IModelDocExtension.SetUserPreferenceToggle"], 1)
        self.assertEqual(names["IModelDoc2.SetSaveFlag"], 1)

    def test_cli_and_result_semantics_enforce_guard_only_fields(self):
        args = build_parser().parse_args(["document", "detailing-line-option-set", self.fields[0], "false",
            "--if-options", json.dumps(self.options()), "--document", self.fx.entry.document_id,
            "--if-update-stamp", "7", "--lease", self.fx.lease["lease_id"], "--json"])
        operation = _typed_operation(args)
        self.assertEqual(operation[0], SET)
        self.assertIs(operation[1]["value"], False)
        self.assertEqual(operation[1]["expected_options"], self.options())
        self.assertTrue(OPERATION_CATALOG[SET].lease_guarded)
        self.assertFalse(OPERATION_CATALOG[SET].temporary_activation)
        with self.proof():
            result = self.call(SET, self.parameters())
        for defect in ("guard", "enabled", "mutation"):
            bad = deepcopy(result)
            if defect == "guard": bad["options"][next(iter(DETAILING_FIELDS))] = True
            elif defect == "enabled": bad["write_enabled"] = False
            else: bad["mutation"]["attempted"] = False
            with self.assertRaises(OperationResultInvalid):
                validate_operation_result(SET, bad)

    def test_sdk_and_mcp_bridge_use_real_operation_schema_without_starting_a_host(self):
        def wire(operation, parameters, **context):
            result = execute_operation(self.fx.app, operation, parameters, documents=self.fx.registry,
                **{key: context[key] for key in ("session_id", "document_id", "expected_update_stamp", "lease_id") if key in context})
            success = result["ok"]
            return {"api_version": "swcli/v1", "request_id": context["request_id"], "duration_ms": 1.0,
                    "success": success, "result": result,
                    **({} if success else {"error": {"code": result["error"]["type"], "message": result["error"]["message"]}})}
        client = Client(endpoint="127.0.0.1:1", session_id="writer")
        with mock.patch("swcli.sdk.client.call_daemon", side_effect=wire):
            read = client.document.detailing_line_options(document_id=self.fx.entry.document_id).require_result()
            self.assertFalse(read["write_enabled"])
            response = client.document.detailing_line_option_set(**self.parameters(value=False),
                document_id=self.fx.entry.document_id, expected_update_stamp=7, lease_id=self.fx.lease["lease_id"])
            with self.assertRaises(RemoteError): response.require_result()
            self.assertEqual(response.result["mutation"], dict(attempted=False, may_have_changed=False))
        with mock.patch("swcli.sdk.client.call_daemon") as no_io:
            with self.assertRaises(ValueError):
                client.document.detailing_line_option_set(**self.parameters(expected={}), document_id=self.fx.entry.document_id,
                    expected_update_stamp=7, lease_id=self.fx.lease["lease_id"])
            no_io.assert_not_called()
        bridge = DaemonBridge(endpoint="127.0.0.1:1", session_id="writer")
        with mock.patch("swcli.mcp.call_daemon", side_effect=wire):
            response = bridge.call("execute", {"operation": READ, "parameters": {}, "document_id": self.fx.entry.document_id})
        self.assertTrue(response["success"], response)
        self.assertEqual(response["result"]["options"], self.options())
        self.fx.assert_untouched()


class DetailingConstantsTests(unittest.TestCase):
    def test_symbol_resolution_is_per_profile_and_never_extends_legacy_requirements(self):
        legacy._load_constants.cache_clear()
        self.addCleanup(legacy._load_constants.cache_clear)
        members = [*zip(DETAILING_FIELDS.values(), (901, 902)), ("swDetailingNoOptionSpecified", 0)]
        Descriptor = namedtuple("Descriptor", "memid value")
        info = SimpleNamespace(GetTypeAttr=lambda: SimpleNamespace(typekind=1, cVars=len(members)),
            GetVarDesc=lambda offset: Descriptor(offset, members[offset][1]),
            GetDocumentation=lambda index: (members[index][0],))
        library = SimpleNamespace(GetTypeInfoCount=lambda: 1, GetTypeInfo=lambda index: info)
        com = SimpleNamespace(TKIND_ENUM=1, LoadTypeLib=mock.Mock(return_value=library))
        with mock.patch.dict("sys.modules", {"pythoncom": com}):
            old = legacy._load_constants("portable.tlb")
            self.assertEqual(set(old), set(DETAILING_FIELDS.values()) | {"swDetailingNoOptionSpecified"})
            symbols = tuple(DETAILING_LINE_SNAPSHOT_FIELDS.values())
            with self.assertRaises(RuntimeError): legacy._load_constants("portable.tlb", symbols)
            members.extend(zip(DETAILING_LINE_FIELDS.values(), (903, 904)))
            new = legacy._load_constants("portable.tlb", symbols)
            self.assertEqual(set(new), set(symbols) | {"swDetailingNoOptionSpecified"})
            self.assertEqual(legacy._load_constants("portable.tlb"), old)
            self.assertEqual(com.LoadTypeLib.call_count, 3)


class RestoreFaultApp:
    def __init__(self, original): self.original, self.command = original, False
    def __getattr__(self, name): return getattr(self.original, name)
    @property
    def CommandInProgress(self): return self.command
    @CommandInProgress.setter
    def CommandInProgress(self, value):
        if value is False: raise RuntimeError("late command restoration failure")
        self.command = value


class DetailingLineWorkerTests(unittest.TestCase):
    def worker(self, *, native_failure=False, validator_failure=False):
        case = DetailingLineTests(); case.setUp(); self.addCleanup(case.doCleanups)
        fx = case.fx
        fx.app.GetProcessID = lambda: 1234
        fx.app.CommandInProgress = False
        app = fx.app if validator_failure else RestoreFaultApp(fx.app)
        if native_failure:
            def setter(pref, option, value):
                fx.native[pref] = value
                raise RuntimeError("first native line failure")
            fx.extension.SetUserPreferenceToggle.side_effect = setter
        request = dict(request_id="line-worker-fault", operation=SET, parameters=case.parameters(),
            session_id="writer", document_id=fx.entry.document_id, expected_update_stamp=7,
            lease_id=fx.lease["lease_id"], timeout_ms=600000)
        responses, lifecycle, com, client = mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock()
        real_validate = server.validate_operation_result
        def validate(name, result):
            if validator_failure and result.get("ok"):
                result["document"] = {"poisoned": True}
                raise RuntimeError("late validator failure")
            return real_validate(name, result)
        with case.proof(), mock.patch.dict("sys.modules", {"pythoncom": com, "win32com": mock.Mock(client=client), "win32com.client": client}), \
                mock.patch.object(server, "acquire_resident_app", return_value=(app, True)) as acquire, \
                mock.patch.object(server, "wait_windows_host_ready", return_value=0), \
                mock.patch.object(server, "DocumentRegistry", return_value=fx.registry), \
                mock.patch.object(server, "_describe_app", return_value={}), \
                mock.patch.object(server, "_wait_for_worker_request", side_effect=[request, None]) as wait, \
                mock.patch.object(server, "validate_operation_result", side_effect=validate):
            server._worker_main(mock.Mock(), responses, lifecycle, False, 120, False)
        responses.put.assert_called_once()
        reply = responses.put.call_args.args[0]
        self.assertFalse(reply["success"])
        self.assertEqual(reply["result"]["mutation"], dict(attempted=True, may_have_changed=True))
        validate_operation_result(SET, reply["result"])
        fx.extension.SetUserPreferenceToggle.assert_called_once()
        acquire.assert_called_once()
        com.CoUninitialize.assert_called_once()
        if native_failure:
            self.assertEqual(reply["result"]["error"]["message"], "first native line failure")
            self.assertIn("worker_error", reply["result"]["error"])
        if not validator_failure:
            self.assertEqual(wait.call_count, 1)
            self.assertTrue(any(call.args[0].get("event") == "host-disconnected" for call in lifecycle.put.call_args_list))
        else:
            self.assertNotIn("document", reply["result"])

    def test_real_handler_adapter_restore_failure_keeps_success_or_first_error(self):
        for native_failure in (False, True):
            with self.subTest(native_failure=native_failure): self.worker(native_failure=native_failure)

    def test_late_validator_failure_keeps_minimal_trusted_mutation(self):
        self.worker(validator_failure=True)

    def test_wrong_action_or_untrusted_receipts_are_never_borrowed(self):
        for result in (None, {}, {"action": "document.detailing-option-set", "mutation": dict(attempted=True, may_have_changed=True)},
                       {"action": SET, "mutation": dict(attempted=1, may_have_changed=True)}):
            reply = server._preserve_preference_receipt({}, SET, result, RuntimeError("late fault"))
            self.assertNotIn("result", reply)


if __name__ == "__main__":
    unittest.main()
