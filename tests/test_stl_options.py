"""Portable failure/contract coverage; never substitutes for native evidence."""
from contextlib import ExitStack
from copy import deepcopy
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock
from jsonschema import Draft202012Validator
from swcli.cli import build_parser, _typed_operation
from swcli.daemon.operations import execute_operation
from swcli.hosts import windows_stl_options as adapter
from swcli.operation_schemas import OPERATION_CATALOG, validate_operation_request
from swcli.sdk import Client

OPTIONS = dict(encoding="binary", unit="mm", deviation_mm=0.1, angle_degrees=10)

class StlOptionsContractTests(unittest.TestCase):
    def test_cli_schema_sdk_and_mcp_catalog_share_options(self):
        args = build_parser().parse_args(["document", "export", "curved.stl", "--stl-encoding", "binary",
            "--stl-unit", "mm", "--stl-deviation-mm", "0.1", "--stl-angle-degrees", "10"])
        operation, parameters, *_ = _typed_operation(args)
        self.assertEqual(parameters["stl_options"], OPTIONS)
        self.assertEqual(validate_operation_request(operation, parameters), parameters)
        client = Client()
        with mock.patch.object(client, "_execute", return_value=None) as call:
            client.document.export(output="curved.stl", stl_options=OPTIONS)
        self.assertEqual(call.call_args.args[1]["stl_options"], OPTIONS)
        schema = OPERATION_CATALOG[operation].parameters
        self.assertTrue(Draft202012Validator(schema).is_valid(parameters))
        import swcli.mcp as mcp
        bridge = mcp.DaemonBridge()
        envelope = {"api_version": "1", "request_id": "stl-test", "success": False,
                    "error": {"code": "StlOptionsNotCalibrated", "message": "closed"}}
        # Explicit metadata-only content avoids the unrelated discovery call.
        with mock.patch.object(mcp, "call_daemon", return_value=envelope) as forwarded:
            bridge.call("execute", {"operation": operation,
                "parameters": {**parameters, "include_content": False}, "request_id": "stl-test",
                "document_id": "d-ab12cd", "expected_update_stamp": 7, "lease_id": "l-ab12cd34ef56"})
        self.assertEqual(forwarded.call_args.args[1]["stl_options"], OPTIONS)
        self.assertEqual(forwarded.call_args.kwargs["expected_update_stamp"], 7)
        self.assertEqual(forwarded.call_args.kwargs["lease_id"], "l-ab12cd34ef56")

    def test_closed_complete_finite_bounded_stl_only_contract(self):
        invalid = [{}, {**OPTIONS, "unknown": 1}, {**OPTIONS, "unit": "yard"},
            {**OPTIONS, "deviation_mm": True}, {**OPTIONS, "deviation_mm": 0},
            {**OPTIONS, "deviation_mm": 1.01}, {**OPTIONS, "angle_degrees": 0.49},
            {**OPTIONS, "angle_degrees": float("nan")}, {**OPTIONS, "angle_degrees": float("inf")}]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(ValueError):
                validate_operation_request("document.export", dict(output="a.stl", stl_options=options))
        for suffix in ("glb", "3mf", "amf", "step", "pdf"):
            values = dict(output="a." + suffix, stl_options=OPTIONS)
            with self.assertRaises(ValueError):
                validate_operation_request("document.export", values)
            self.assertFalse(Draft202012Validator(OPERATION_CATALOG["document.export"].parameters).is_valid(values))

    def test_missing_context_and_public_calls_fail_before_com(self):
        app = SimpleNamespace()
        with self.assertRaisesRegex(ValueError, "explicit"):
            execute_operation(app, "document.export", dict(output="a.stl", stl_options=OPTIONS))
        with mock.patch.object(adapter, "_HOST", None):
            with self.assertRaisesRegex(adapter.StlOptionsError, "public writes are disabled"):
                execute_operation(app, "document.export", dict(output="a.stl", stl_options=OPTIONS),
                    documents=object(), document_id="d-ab12cd", expected_update_stamp=1, lease_id="l-ab12cd34ef56")

class StlPreferenceTransactionTests(unittest.TestCase):
    def setUp(self):
        self.codes = {name: i for i, name in enumerate(adapter.PREFERENCES)}
        self.codes.update({name: i for i, name in enumerate(adapter.UNIT_NAMES.values())})
        self.codes["swSTLQuality_Custom"] = 3
        self.state = {name: (False if kind == "Toggle" else 2 if kind == "IntegerValue" else 0.25)
                      for name, kind in adapter.PREFERENCES.items()}
        self.original = deepcopy(self.state)
        self.calls = []
        self.write_failure = self.restore_failure = None
        self.writes = 0
        app = SimpleNamespace()
        for kind in ("Toggle", "IntegerValue", "DoubleValue"):
            def getter(code, kind=kind):
                name = next(n for n, k in adapter.PREFERENCES.items() if k == kind and self.codes[n] == code)
                self.calls.append(("read", name))
                return self.state[name]
            def setter(code, value, kind=kind):
                name = next(n for n, k in adapter.PREFERENCES.items() if k == kind and self.codes[n] == code)
                self.calls.append(("write", name, value))
                self.writes += 1
                self.state[name] = value  # COM may mutate even when it raises.
                if self.writes == self.write_failure or (self.writes > 8 and name == self.restore_failure):
                    raise RuntimeError("setter original error")
                return True
            setattr(app, "GetUserPreference" + kind, getter)
            setattr(app, "SetUserPreference" + kind, setter)
        self.app = app
        self.evidence = {}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(adapter, "require_isolation"))
        self.stack.enter_context(mock.patch.object(adapter, "constants", return_value=self.codes))
        self.stack.enter_context(mock.patch.object(adapter, "_POISONED", False))
        self.mutex = SimpleNamespace(CreateMutex=mock.Mock(return_value=7), WaitForSingleObject=mock.Mock(return_value=0),
            ReleaseMutex=mock.Mock(), WAIT_OBJECT_0=0, WAIT_ABANDONED=128)
        self.stack.enter_context(mock.patch.dict(sys.modules, {"win32event": self.mutex,
            "win32api": SimpleNamespace(CloseHandle=mock.Mock())}))

    def test_applies_real_stl_values_then_restores_whole_vector(self):
        with adapter.stl_preferences(self.app, OPTIONS, self.evidence):
            self.assertTrue(self.state["swSTLBinaryFormat"])
            self.assertEqual(self.state["swExportStlUnits"], self.codes["swMM"])
            self.assertEqual(self.state["swSTLDeviation"], 0.0001)
            self.assertEqual(self.state["swSTLAngleTolerance"], math.radians(10))
        self.assertTrue(self.evidence["restored"])
        self.assertEqual(self.state, self.original)
        self.assertEqual(self.writes, 16)

    def test_native_failure_is_preserved_even_if_restore_also_fails(self):
        self.restore_failure = "swSTLQuality"
        with self.assertRaisesRegex(ValueError, "first native failure"):
            with adapter.stl_preferences(self.app, OPTIONS, self.evidence):
                raise ValueError("first native failure")
        self.assertFalse(self.evidence["restored"])
        self.assertTrue(self.evidence["cleanup_errors"])
        self.assertTrue(adapter._POISONED)

    def test_partial_setter_failure_restores_and_does_not_export_or_retry(self):
        self.write_failure = 3
        with self.assertRaisesRegex(RuntimeError, "setter original error"):
            with adapter.stl_preferences(self.app, OPTIONS, self.evidence):
                self.fail("export must not execute")
        self.assertTrue(self.evidence["restored"])
        self.assertEqual(self.writes, 11)

    def test_mutex_contention_and_abandonment_never_write(self):
        for status in (258, 128):
            self.mutex.WaitForSingleObject.return_value = status
            with self.assertRaises(adapter.StlOptionsError):
                with adapter.stl_preferences(self.app, OPTIONS, self.evidence):
                    self.fail("mutex failure must not export")
            self.assertEqual(self.writes, 0)

    def test_readback_mismatch_fails_without_export_and_restores(self):
        original = self.app.SetUserPreferenceToggle
        def ignore(code, value):
            return True
        self.app.SetUserPreferenceToggle = ignore
        with self.assertRaisesRegex(adapter.StlOptionsError, "exact requested"):
            with adapter.stl_preferences(self.app, OPTIONS, self.evidence):
                self.fail("readback failure must not export")
        self.assertTrue(self.evidence["restored"])


class StlDaemonGuardsTests(unittest.TestCase):
    def test_stale_stamp_and_other_session_lease_never_call_export(self):
        from test_document_units import DocumentUnitsTests
        from swcli.daemon.operations import DocumentUpdateConflict
        from swcli.daemon.documents import DocumentLeaseConflict
        fixture = DocumentUnitsTests()
        fixture.setUp()
        values = dict(output="a.stl", stl_options=OPTIONS)
        with mock.patch.object(adapter, "require_isolation"), mock.patch(
                "swcli.daemon.operations.export_active_windows_document") as export:
            with self.assertRaises(DocumentUpdateConflict):
                execute_operation(fixture.app, "document.export", values, documents=fixture.documents,
                    document_id=fixture.entry.document_id, expected_update_stamp=6,
                    lease_id=fixture.lease["lease_id"], session_id="writer")
            with self.assertRaises(DocumentLeaseConflict):
                execute_operation(fixture.app, "document.export", values, documents=fixture.documents,
                    document_id=fixture.entry.document_id, expected_update_stamp=7,
                    lease_id=fixture.lease["lease_id"], session_id="other")
            export.assert_not_called()
            fixture.app.ActivateDoc3.assert_not_called()

    def test_readonly_and_wrong_format_reject_before_preference_writes(self):
        import tempfile
        from test_windows_mesh_exports import WindowsMeshExportTests
        from swcli.hosts import windows_documents as docs
        # Adapter runs through existing platform and pythoncom mock boundaries.
        case = WindowsMeshExportTests()
        original = docs.export_active_windows_document
        for readonly in (True, False):
            def with_options(output, **kwargs):
                doc = kwargs["app"].ActiveDoc
                doc.IsOpenedReadOnly = lambda: readonly
                doc.IsOpenedViewOnly = lambda: False
                return original(output, stl_options=OPTIONS, **kwargs)
            with mock.patch.object(docs, "export_active_windows_document", side_effect=with_options), mock.patch.object(
                    docs, "stl_preferences") as transaction:
                result = case.export("STL" if readonly else "GLB", b"not exported")
                self.assertEqual(result["error"]["type"], "DocumentReadOnly" if readonly else "StlFormatRequired")
                transaction.assert_not_called()
                self.assertEqual(case.saved, [])


class StlExportFailureEvidenceTests(unittest.TestCase):
    def export(self, *, restored=True, encoding="binary", save_error=0, native_failure=False):
        from contextlib import contextmanager
        from test_windows_mesh_exports import WindowsMeshExportTests
        from test_export_validation import binary_stl
        from swcli.hosts import windows_documents as docs
        case = WindowsMeshExportTests()
        original = docs.export_active_windows_document
        def with_options(output, **kwargs):
            doc = kwargs["app"].ActiveDoc
            doc.IsOpenedReadOnly = lambda: False
            doc.IsOpenedViewOnly = lambda: False
            doc.GetUpdateStamp = lambda: 5
            doc.GetActiveConfiguration = lambda: SimpleNamespace(Name="Default")
            return original(output, stl_options={**OPTIONS, "encoding": encoding}, **kwargs)
        @contextmanager
        def transaction(app, options, evidence):
            evidence.update(mutation_attempted=True, restored=False, cleanup_errors=[])
            try:
                yield
            finally:
                evidence["restored"] = restored
                if not restored:
                    evidence["cleanup_errors"].append({"preference": "swSTLQuality", "error": "restore failed"})
        with mock.patch.object(docs, "export_active_windows_document", side_effect=with_options), mock.patch.object(
                docs, "stl_preferences", side_effect=transaction):
            result = case.export("STL", binary_stl(), save_error=save_error, native_failure=native_failure)
        return result, case

    def test_original_native_status_survives_restore_failure_and_target_is_preserved(self):
        for parameters, code in ((dict(save_error=1), "ExportFailed"), (dict(native_failure=True), "RuntimeError")):
            result, case = self.export(restored=False, **parameters)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], code)
            self.assertEqual(case.output, b"previous valid artifact")
            self.assertEqual(len(case.saved), 1)
            self.assertTrue(result["stl_source_state"]["unchanged"])
            self.assertTrue(result["stl_preferences"]["cleanup_errors"])

    def test_encoding_mismatch_and_restore_failure_never_replace_existing_output(self):
        for parameters, code in ((dict(encoding="ascii"), "ExportVerificationFailed"),
                                 (dict(restored=False), "ExportPreferenceRestoreFailed")):
            result, case = self.export(**parameters)
            self.assertEqual(result["error"]["type"], code)
            self.assertFalse(result["ok"])
            self.assertEqual(case.output, b"previous valid artifact")
            self.assertEqual(len(case.saved), 1)
