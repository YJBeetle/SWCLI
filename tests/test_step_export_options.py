"""STEP contracts and preference transaction failure boundaries (portable)."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace, ModuleType
import tempfile
import unittest
from unittest import mock

from swcli.hosts import windows_step_export as step, windows_documents as docs
from swcli.operation_schemas import validate_operation_request, OPERATION_CATALOG
from swcli.result_schemas import validate_operation_result
from swcli.cli import build_parser, _typed_operation


CONSTANTS = {"swStepAP": 999, "swStepExportPreference": 777,
             "swAcisOutputAsSolidAndSurface": 0, "swAcisOutputAs3DCurves": 1,
             "swAcisOutputAs3DCurves_IncludeSketchEnts": 2}


def payload(protocol="ap214", geometry="solid-surface"):
    schema = "AUTOMOTIVE_DESIGN" if protocol == "ap214" else "CONFIG_CONTROL_DESIGN"
    entity = "MANIFOLD_SOLID_BREP" if geometry == "solid-surface" else "GEOMETRIC_CURVE_SET"
    return f"ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('{schema}'));\nENDSEC;\nDATA;\n#1={entity}('',());\nENDSEC;\nEND-ISO-10303-21;\n".encode()


class StepExportTests(unittest.TestCase):
    def setUp(self):
        self.values = {999: 203, 777: 0}
        self.writes = []
        self.app = SimpleNamespace(Visible=False, RevisionNumber="34.0")
        self.app.GetUserPreferenceIntegerValue = lambda key: self.values[key]
        self.app.SetUserPreferenceIntegerValue = self.setter
        self.document = SimpleNamespace(SketchManager=SimpleNamespace(ActiveSketch=None))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(step, "read_step_constants", return_value=CONSTANTS))
        self.stack.enter_context(mock.patch.object(step, "_require_writable"))
        self.stack.enter_context(mock.patch.object(step, "_state", return_value=(1, 5, False, "Default")))
        self.stack.enter_context(mock.patch.object(step, "_verify_metadata_state"))
        self.app.ActiveDoc = self.document

    def setter(self, key, value):
        self.writes.append((key, value))
        self.values[key] = value
        return True

    def scope(self, result, **kwargs):
        self.stack.enter_context(step.step_host_scope(self.app, isolated=True, calibration=True))
        return step.step_preferences(self.app, self.document, "ap214", "wireframe", result)

    def test_complete_snapshot_setting_readback_and_finally_restore(self):
        result = {}
        with self.scope(result):
            self.assertEqual(self.values, {999: 214, 777: 1})
        self.assertEqual(self.values, {999: 203, 777: 0})
        self.assertTrue(result["step_preferences"]["restored"])
        self.assertEqual(self.writes, [(999, 214), (777, 1), (777, 0), (999, 203)])

    def test_native_failure_identity_survives_restore_failure(self):
        result, failure = {}, ValueError("first native failure")
        def setter(key, value):
            if value == 0:
                raise RuntimeError("restore failed")
            return self.setter(key, value)
        self.app.SetUserPreferenceIntegerValue = setter
        with self.assertRaises(ValueError) as raised:
            with self.scope(result):
                raise failure
        self.assertIs(raised.exception, failure)
        self.assertIn("preference_restore_errors", result)
        self.assertFalse(result["step_preferences"]["restored"])
        self.assertEqual(self.values[999], 203)  # Other preference still restored.

    def test_numeric_native_failure_preserved_when_restore_fails(self):
        result = {}
        def setter(key, value):
            if value == 0:
                return False
            return self.setter(key, value)
        self.app.SetUserPreferenceIntegerValue = setter
        with self.scope(result):
            result["error"] = {"type": "ExportFailed", "save_errors": 1}
        self.assertEqual(result["error"]["type"], "ExportFailed")
        self.assertIn("preference_restore_errors", result)

    def test_restore_failure_after_success_is_failure(self):
        result = {}
        def setter(key, value):
            if value == 0:
                return False
            return self.setter(key, value)
        self.app.SetUserPreferenceIntegerValue = setter
        with self.assertRaises(step.StepExportError) as raised:
            with self.scope(result):
                pass
        self.assertEqual(raised.exception.code, "StepPreferenceRestoreFailed")

    def test_rejected_or_throwing_setter_restores_even_after_partial_mutation(self):
        for throws in (False, True):
            self.values = {999: 203, 777: 0}
            result = {}
            def setter(key, value):
                self.setter(key, value)
                if value == 214:
                    if throws:
                        raise ValueError("setter mutated then threw")
                    return False
                return True
            self.app.SetUserPreferenceIntegerValue = setter
            with self.assertRaises((ValueError, step.StepExportError)):
                with self.scope(result):
                    self.fail("save must not run")
            self.assertEqual(self.values, {999: 203, 777: 0})
            self.assertTrue(result["step_preferences"]["restored"])

    def test_complete_cas_conflict_and_unreadable_values_prevent_all_writes(self):
        for read in (mock.Mock(side_effect=[203, 0, 214, 0]), lambda key: True):
            self.app.GetUserPreferenceIntegerValue = read
            with self.assertRaises(step.StepExportError):
                with self.scope({}):
                    self.fail("save must not run")
            self.assertEqual(self.writes, [])

    def test_ownership_visibility_and_calibration_fail_closed(self):
        for isolated, calibration, visible, code in (
            (False, True, False, "StepIsolationRequired"),
            (True, True, True, "StepIsolationRequired"),
            (True, False, False, "StepCalibrationRequired"),
        ):
            self.app.Visible = visible
            with step.step_host_scope(self.app, isolated=isolated, calibration=calibration):
                with self.assertRaises(step.StepExportError) as raised:
                    with step.step_preferences(self.app, self.document, "ap214", "wireframe", {}):
                        self.fail("uncalibrated/shared/visible save must not run")
            self.assertEqual(raised.exception.code, code)
        self.assertEqual(self.writes, [])

    def test_no_options_never_access_preferences(self):
        with step.step_preferences(object(), object(), None, None, {}):
            pass
        self.assertEqual(self.writes, [])

    def test_file_schema_entity_family_and_termination(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "part.step"
            for protocol in step.STEP_PROTOCOLS:
                for geometry in step.STEP_GEOMETRIES:
                    path.write_bytes(payload(protocol, geometry))
                    self.assertEqual(step.verify_step_output(path, protocol, geometry)["protocol"], protocol)
            for data in (payload("ap203"), payload().replace(b"END-ISO-10303-21;", b""),
                         payload("ap214", "wireframe")):
                path.write_bytes(data)
                with self.assertRaises(step.StepExportError):
                    step.verify_step_output(path, "ap214", "solid-surface")

    def test_contract_requires_pair_extension_lease_stamp_and_no_ap242(self):
        valid = {"output": "part.STP", "step_protocol": "ap214", "step_geometry": "wireframe"}
        context = {"lease_id": "l-ab12cd34ef56", "expected_update_stamp": 5}
        self.assertEqual(validate_operation_request("document.export", valid, **context), valid)
        for bad in ({**valid, "step_protocol": "ap242"}, {**valid, "step_geometry": "solid"},
                    {**valid, "output": "part.stl"}, {k:v for k,v in valid.items() if k != "step_geometry"},
                    {**valid, "step_protocol": None}, {**valid, "step_calibration": True}):
            with self.assertRaises((ValueError, step.StepExportError)):
                validate_operation_request("document.export", bad, **context)
        for partial in ({}, {"lease_id": context["lease_id"]}, {"expected_update_stamp": 5}):
            with self.assertRaises(ValueError):
                validate_operation_request("document.export", valid, **partial)
        validate_operation_request("document.export", {"output": "part.step"})

    def test_schema_cli_sdk_and_mcp_expose_same_parameter_contract(self):
        from jsonschema import Draft202012Validator
        from swcli.sdk import Client
        from swcli.mcp import DaemonBridge
        import inspect
        schema = OPERATION_CATALOG["document.export"].parameters
        params = {"output": "part.STEP", "step_protocol": "ap214", "step_geometry": "solid-surface"}
        Draft202012Validator(schema).validate(params)
        self.assertIn("step_protocol", inspect.signature(Client().document.export).parameters)
        args = build_parser().parse_args(["document", "export", "part.STEP", "--step-protocol", "ap214",
                                         "--step-geometry", "solid-surface"])
        self.assertEqual(_typed_operation(args)[1]["step_geometry"], "solid-surface")
        def reply(operation, parameters, **context):
            return {"api_version": "swcli/v1", "request_id": context["request_id"], "success": False,
                    "duration_ms": 1, "error": {"code": "StepCalibrationRequired", "message": "uncalibrated"}}
        with mock.patch("swcli.mcp.call_daemon", side_effect=reply) as wire:
            result = DaemonBridge().call("execute", {"operation": "document.export",
                "parameters": {**params, "include_content": False},
                "lease_id": "l-ab12cd34ef56", "expected_update_stamp": 5})
            self.assertFalse(result["success"])
            self.assertEqual(wire.call_args.args[1]["step_protocol"], "ap214")
            self.assertEqual(wire.call_args.kwargs["expected_update_stamp"], 5)
            self.assertEqual(result["error"]["code"], "StepCalibrationRequired")
        with mock.patch("swcli.sdk.client.call_daemon") as wire:
            with self.assertRaises(ValueError):
                Client().document.export(**params)
            wire.assert_not_called()

    def test_existing_output_preserved_when_step_output_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "part.step"
            path.write_bytes(b"old output")
            document = SimpleNamespace(ClearSelection2=mock.Mock(), SaveAs3=lambda name, *_: (Path(name).write_bytes(payload("ap203")), 0)[1])
            win32 = ModuleType("win32com"); win32.client = ModuleType("win32com.client")
            with mock.patch.object(docs.sys, "platform", "win32"), \
                    mock.patch.dict("sys.modules", {"pythoncom": ModuleType("pythoncom"), "win32com": win32, "win32com.client": win32.client}), \
                    mock.patch.object(docs, "_export_source_state", return_value={"document": {"type": 1, "path": "source.SLDPRT"}}), \
                    mock.patch.object(docs, "_export_source_warnings", return_value=[]), \
                    mock.patch.object(docs, "step_preferences", return_value=ExitStack()):
                result = docs.export_active_windows_document(str(path), app=self.app, document=document,
                    overwrite=True, step_protocol="ap214", step_geometry="solid-surface")
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"]["type"], "StepOutputMismatch")
            self.assertEqual(result["mutation"], {"attempted": True, "may_have_changed": True})
            self.assertEqual(path.read_bytes(), b"old output")
            self.assertEqual(list(Path(directory).iterdir()), [path])
            validate_operation_result("document.export", result)

    def test_worker_quarantines_host_after_preference_restore_failure(self):
        from test_native_sequence import NativeSequenceTests
        from swcli.daemon import server
        helper = NativeSequenceTests()
        app = SimpleNamespace(CommandInProgress=False, GetProcessID=lambda: 1234,
                              RevisionNumber="34.0", ActiveDoc=object())
        request = {"request_id": "first", "operation": "document.export", "parameters": {}}
        failure = {"ok": False, "error": {"type": "ExportFailed", "message": "first native error"},
                   "preference_restore_errors": [{"type": "RuntimeError", "message": "restore failed"}]}
        responses, lifecycle, wait = helper.run_worker(app, True, lambda *a, **k: failure, [request, None])
        self.assertEqual(wait.call_count, 1)
        self.assertEqual(responses.put.call_args.args[0]["result"], failure)
        self.assertEqual(responses.put.call_args.args[0]["error"]["code"], "ExportFailed")
        self.assertEqual(lifecycle.put.call_args.args[0]["event"], "host-disconnected")

    def test_native_preference_drift_during_export_is_detected_and_restored(self):
        result = {}
        with self.assertRaises(step.StepExportError) as raised:
            with self.scope(result):
                self.values[999] = 203
        self.assertEqual(raised.exception.code, "StepPreferenceReadbackFailed")
        self.assertEqual(self.values, {999: 203, 777: 0})
        self.assertTrue(result["step_preferences"]["restored"])

    def test_installed_typelib_enum_ownership_and_completeness(self):
        def enum(name, values):
            pairs = list(values.items())
            return SimpleNamespace(
                GetTypeAttr=lambda: SimpleNamespace(typekind=0, cVars=len(pairs)),
                GetDocumentation=lambda index: (name if index == -1 else pairs[index][0],),
                GetVarDesc=lambda index: SimpleDescriptor(index, pairs[index][1]))
        class SimpleDescriptor:
            def __init__(self, index, value):
                self.index, self.value = index, value
            def __getitem__(self, index):
                return self.index
        enums = [enum("swUserPreferenceIntegerValue_e", {"swStepAP": 999, "swStepExportPreference": 777}),
                 enum("swAcisOutputGeometryPreference_e", {k:v for k,v in CONSTANTS.items() if k.startswith("swAcis")})]
        library = SimpleNamespace(GetTypeInfoCount=lambda: len(enums), GetTypeInfo=lambda index: enums[index])
        pythoncom = SimpleNamespace(LoadTypeLib=lambda path: library, TKIND_ENUM=0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "swconst.tlb"
            path.touch()
            with mock.patch.dict("sys.modules", {"pythoncom": pythoncom}):
                # Bypass this test class's portable stand-in to inspect real reader.
                self.stack.close()
                self.assertEqual(step.read_step_constants(path), CONSTANTS)
                enums.pop()
                with self.assertRaises(step.StepExportError):
                    step.read_step_constants(path)


    def test_unknown_original_preference_fails_before_any_setter(self):
        for values in ({999: 242, 777: 0}, {999: 203, 777: 99}):
            self.values = values
            with self.assertRaises(step.StepExportError) as raised:
                with self.scope({}):
                    self.fail("unknown original preference must not enter mutation scope")
            self.assertEqual(raised.exception.code, "StepPreferenceUnsupported")
            self.assertEqual(self.writes, [])


    def test_revision_evidence_never_enables_other_native_runtimes(self):
        with mock.patch.object(step, "VALIDATED_REVISIONS", frozenset({"34.0"})), \
                mock.patch.object(step, "_native_windows_runtime", return_value=False):
            with step.step_host_scope(self.app, isolated=True):
                with self.assertRaises(step.StepExportError) as raised:
                    with step.step_preferences(self.app, self.document, "ap214", "wireframe", {}):
                        self.fail("unvalidated Wine/non-Windows runtime must not write preferences")
        self.assertEqual(raised.exception.code, "StepNativePlatformRequired")
        self.assertEqual(self.writes, [])


    def test_unsaved_source_rejected_before_preferences_or_native_save(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "part.step"
            output.write_bytes(b"original")
            document = SimpleNamespace(SaveAs3=mock.Mock())
            win32 = ModuleType("win32com"); win32.client = ModuleType("win32com.client")
            with mock.patch.object(docs.sys, "platform", "win32"), \
                    mock.patch.dict("sys.modules", {"pythoncom": ModuleType("pythoncom"), "win32com": win32, "win32com.client": win32.client}), \
                    mock.patch.object(docs, "_export_source_state", return_value={"document": {"type": 1, "path": ""}}):
                result = docs.export_active_windows_document(str(output), app=self.app, document=document,
                    overwrite=True, step_protocol="ap214", step_geometry="solid-surface")
            self.assertEqual(result["error"]["type"], "SourceNotClean")
            self.assertEqual(result["mutation"], {"attempted": False, "may_have_changed": False})
            self.assertEqual(output.read_bytes(), b"original")
            document.SaveAs3.assert_not_called()
            self.assertEqual(self.writes, [])
