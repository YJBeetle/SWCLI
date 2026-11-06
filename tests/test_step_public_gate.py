"""Offline public acceptance harness safety; never native acceptance evidence."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location("step_gate_" + name.replace("-", "_"), ROOT / "scripts/ci" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StepPublicGateTests(unittest.TestCase):
    def test_first_cli_failure_is_preserved_and_no_host_or_export_retry(self):
        module = script("verify-step-export-public.py")
        process = SimpleNamespace(pid=1234, returncode=0, poll=lambda: None, wait=lambda **kw: 0)
        handle = mock.Mock()
        modules = {"win32api": SimpleNamespace(OpenProcess=lambda *args: handle),
                   "win32con": SimpleNamespace(SYNCHRONIZE=1),
                   "win32event": SimpleNamespace(WaitForSingleObject=lambda *args: 0, WAIT_OBJECT_0=0)}
        def run(arguments, **kwargs):
            if "status" in arguments:
                payload = {"success": True, "result": {"host": {"process_id": 5678,
                    "revision": "native-revision", "owned_by_daemon": True, "visible": False,
                    "shared_interactive": False}}}
                code = 0
            elif "create-box" in arguments:
                payload = {"ok": False, "error": {"type": "OriginalFailure", "message": "native fixture failed"}}
                code = 1
            else:
                self.assertIn("stop", arguments)
                payload = {"success": True}
                code = 0
            return SimpleNamespace(returncode=code, stdout=json.dumps(payload).encode(), stderr=b"original stderr")
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.dict("sys.modules", modules), \
                mock.patch.object(module.subprocess, "Popen", return_value=process) as start, \
                mock.patch.object(module.subprocess, "run", side_effect=run) as command, \
                mock.patch.object(module.socket, "create_connection", return_value=mock.MagicMock()):
            output = Path(directory) / "evidence"
            self.assertEqual(module.main(["--output-dir", str(output)]), 1)
            report = json.loads((output / "report.json").read_text())
            self.assertFalse(report["success"])
            self.assertIn("OriginalFailure", report["failure"]["message"])
            self.assertEqual(report["cleanup_errors"], [])
            self.assertEqual(start.call_count, 1)
            self.assertEqual(command.call_count, 3)
            self.assertEqual((output / "create-box.stderr.log").read_text(), "original stderr")
            handle.Close.assert_called_once()

    def test_public_exports_parse_real_cli_with_complete_document_lease_and_cas_context(self):
        from swcli.cli import build_parser, _typed_operation
        module = script("verify-step-export-public.py")
        parser = build_parser()
        for protocol in ("ap203", "ap214"):
            for geometry in ("solid-surface", "wireframe", "wireframe-sketches"):
                arguments = ["--endpoint", "127.0.0.1:51742", "--session", "step-public-session",
                    "--request-timeout", "600", "document", "export", "output.STEP",
                    "--step-protocol", protocol, "--step-geometry", geometry,
                    *module.document_context("d-testdoc", "l-testlease", 163), "--json"]
                parsed = parser.parse_args(arguments)
                self.assertEqual((parsed.document_id, parsed.lease_id, parsed.expected_update_stamp),
                                 ("d-testdoc", "l-testlease", 163))
                operation, parameters = _typed_operation(parsed)[:2]
                self.assertEqual(operation, "document.export")
                self.assertEqual(parameters["step_protocol"], protocol)
                self.assertEqual(parameters["step_geometry"], geometry)

    def test_public_output_digest_mismatch_blocks_native_readback(self):
        module = script("verify-step-export-calibration.py")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            target = output / "actual.step"
            target.write_bytes(b"different actual content")
            (output / "source-public-report.json").write_text(json.dumps({"outputs": [{
                "path": str(target), "sha256": "not-the-actual-digest"}]}))
            native_call = mock.Mock()
            with self.assertRaisesRegex(RuntimeError, "public STEP digest mismatch"):
                module.readback_case(object(), output, {}, None, None, native_call, {}, {}, {}, profile_kind="0")
            native_call.assert_not_called()

    def test_cli_transport_metadata_is_retained_but_not_confused_with_native_schema(self):
        module = script("verify-step-export-public.py")
        result = {"ok": True, "action": "document.export", "output": "part.step",
                  "artifact": {"kind": "cad-export", "format": "STEP", "path": "part.step", "size_bytes": 100},
                  "request_id": "recorded-request", "replayed": False}
        module.validate_public_result("document.export", result)
        self.assertEqual(result["request_id"], "recorded-request")
        from swcli.result_schemas import OperationResultInvalid
        with self.assertRaises(OperationResultInvalid):
            module.validate_public_result("document.export", {**result, "unknown_native_field": 1})

    def test_approved_physical_comparison_accepts_roundoff_and_rejects_geometry_changes(self):
        from copy import deepcopy
        module = script("verify-step-export-calibration.py")
        centroid = {"x": 0.0, "y": 7.72035238382826e-17, "z": 5.0}
        before = {"ok": True, "action": "document.measure", "method": "native-body-mass-properties",
                  "metrics": {"solid_body_count": 1, "volume_mm3": 11999.999999999998,
                              "surface_area_mm2": 3800.0, "centroid_mm": centroid},
                  "bodies": [{"index": 0, "volume_mm3": 11999.999999999998,
                              "surface_area_mm2": 3800.0, "centroid_mm": centroid}]}
        after = deepcopy(before)
        after["metrics"]["centroid_mm"]["y"] = -1.9852334701272667e-16
        module.verify_reopened_geometry(before, after, "solid-surface")
        for field, value in (("solid_body_count", 2), ("volume_mm3", 12001), ("surface_area_mm2", 3801)):
            changed = deepcopy(after)
            changed["metrics"][field] = value
            with self.assertRaises(RuntimeError):
                module.verify_reopened_geometry(before, changed, "solid-surface")
        for value in (1e-6, float("nan"), float("inf")):
            changed = deepcopy(after)
            changed["metrics"]["centroid_mm"]["y"] = value
            with self.assertRaises(RuntimeError):
                module.verify_reopened_geometry(before, changed, "solid-surface")
        wire = {"segment_count": 12, "lengths_mm": [10.0] * 4 + [30.0] * 4 + [40.0] * 4,
                "total_length_mm": 320.0}
        roundoff = deepcopy(wire)
        roundoff["lengths_mm"][0] += 1e-13
        module.verify_reopened_geometry(wire, roundoff, "wireframe")
        for changed in ({**wire, "segment_count": 13}, {**wire, "total_length_mm": 321},
                        {**wire, "lengths_mm": [10.000001] + wire["lengths_mm"][1:]}):
            with self.assertRaises(RuntimeError):
                module.verify_reopened_geometry(wire, changed, "wireframe")

    def test_observer_import_profile_is_scoped_and_first_failure_survives_restore_error(self):
        module = script("verify-step-export-calibration.py")
        names = list(module.IMPORT_PROFILE)
        constants = {name: index + 1000 for index, name in enumerate(names)}
        original = {1000: True, 1001: True, 1002: False}
        values = dict(original)
        writes = []
        def setter(key, value):
            writes.append((key, value))
            values[key] = value
            return None
        app = SimpleNamespace(GetDocumentCount=0, GetUserPreferenceToggle=lambda key: values[key],
                              SetUserPreferenceToggle=setter)
        case = {}
        call = lambda name, function: function()
        with module.observer_import_preferences(app, constants, call, case):
            self.assertEqual(values, {constants[name]: value for name, value in module.IMPORT_PROFILE.items()})
        self.assertEqual(values, original)
        self.assertTrue(case["observer_import_preferences"]["restored"])
        self.assertEqual(len(writes), 4)  # Two changed settings, once each way.
        first = RuntimeError("original LoadFile4 readback failure")
        def bad_restore(key, value):
            if key == 1002 and value is False:
                raise RuntimeError("restore failure")
            return setter(key, value)
        app.SetUserPreferenceToggle = bad_restore
        case = {}
        with self.assertRaises(RuntimeError) as raised:
            with module.observer_import_preferences(app, constants, call, case):
                raise first
        self.assertIs(raised.exception, first)
        self.assertIn("restore_errors", case["observer_import_preferences"])
        self.assertFalse(case["success"])
        self.assertTrue(values[1000])  # Other original preference still restored.

    def test_void_import_setter_requires_effective_readback_before_import(self):
        module = script("verify-step-export-calibration.py")
        constants = {name: index + 2000 for index, name in enumerate(module.IMPORT_PROFILE)}
        values = {2000: True, 2001: True, 2002: False}
        app = SimpleNamespace(GetDocumentCount=0, GetUserPreferenceToggle=lambda key: values[key],
                              SetUserPreferenceToggle=lambda *args: None)
        case = {}
        with self.assertRaisesRegex(RuntimeError, "observer import preference readback differs"):
            with module.observer_import_preferences(app, constants, lambda name, fn: fn(), case):
                self.fail("ignored setter must not import generated output")
        self.assertTrue(case["observer_import_preferences"]["restored"])

    def test_fixture_oracle_includes_and_independently_checks_construction_diagonals(self):
        module = script("verify-step-export-calibration.py")
        corners = [(-20.0, -15.0, 0.0), (20.0, -15.0, 0.0), (20.0, 15.0, 0.0), (-20.0, 15.0, 0.0)]
        pairs = [(corners[i], corners[(i+1) % 4], False) for i in range(4)]
        pairs += [(corners[0], corners[2], True), (corners[1], corners[3], True)]
        segments = [{"construction": construction, "geometry": {"kind": "line",
            "start_mm": dict(zip("xyz", first)), "end_mm": dict(zip("xyz", second))}}
            for first, second, construction in pairs]
        source = {"ok": True, "editing": False, "geometry_complete": True, "segment_count": 6,
                  "profile_segment_count": 4, "segments": segments}
        checked = module.verify_source_sketch(source)
        self.assertEqual(checked["source_total_length_mm"], 240.0)
        lengths = [10.0] * 4 + [30.0] * 6 + [40.0] * 6 + [50.0] * 2
        wire = {"segment_count": 18, "lengths_mm": lengths, "total_length_mm": 560.0}
        module.verify_wire_geometry(wire, "wireframe-sketches")
        for bad in ({"segment_count": 16, "lengths_mm": lengths[:-2], "total_length_mm": 460.0},
                    {**wire, "segment_count": 19}, {**wire, "total_length_mm": 460.0}):
            with self.assertRaises(RuntimeError):
                module.verify_wire_geometry(bad, "wireframe-sketches")
        with self.assertRaises(RuntimeError):
            module.verify_source_sketch({**source, "segment_count": 4, "segments": segments[:4]})
