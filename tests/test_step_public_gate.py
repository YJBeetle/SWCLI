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

    def test_wire_observer_reads_absorbed_sketches_once_and_keeps_incomplete_evidence(self):
        module = script("verify-step-export-calibration.py")
        expected = [10.0]*4 + [30.0]*4 + [40.0]*4
        def feature(identity, lengths=(), kind="3DProfileFeature"):
            return SimpleNamespace(GetID=identity,GetTypeName2=kind,Name="feature-"+str(identity),
                GetSpecificFeature2=SimpleNamespace(GetSketchSegments=[SimpleNamespace(GetLength=v/1000) for v in lengths]),
                GetFirstSubFeature=None,GetNextSubFeature=None,GetNextFeature=None)
        parent = feature(1,kind="ImportedCurve")
        top_sketch = feature(2,expected[:9])
        absorbed_sketch = feature(3,expected[9:])
        parent.GetFirstSubFeature = absorbed_sketch
        parent.GetNextFeature = top_sketch
        document = SimpleNamespace(FirstFeature=parent,GetBodies2=lambda *args:())
        observed = module.read_wireframe(document)
        self.assertEqual(observed["segment_count"],12)
        self.assertEqual(observed["lengths_mm"],expected)
        self.assertEqual(len(observed["feature_inventory"]),3)
        module.verify_wire_geometry(observed,"wireframe")
        top_sketch.GetNextFeature = absorbed_sketch  # Same native ID via two paths.
        self.assertEqual(module.read_wireframe(document)["segment_count"],12)
        # The same nine real segments still fail if the missing three are absent.
        top_sketch.GetNextFeature = parent.GetFirstSubFeature = None
        partial = {}
        with self.assertRaisesRegex(RuntimeError,"at least its twelve edges"):
            module.read_wireframe(document,partial)
        self.assertEqual(partial["segment_count"],9)
        self.assertEqual(partial["lengths_mm"],expected[:9])
        self.assertEqual(len(partial["feature_inventory"]),2)
        # Corrupt cyclic graphs also fail, retaining the first observation.
        parent.GetFirstSubFeature = absorbed_sketch
        absorbed_sketch.GetNextSubFeature = absorbed_sketch
        with self.assertRaisesRegex(RuntimeError,"sibling cycle"):
            module.read_wireframe(document,{})

    def test_reference_curve_observer_uses_real_edge_range_once_and_keeps_exact_counts(self):
        module = script("verify-step-export-calibration.py")
        expected = [10.0]*4+[30.0]*4+[40.0]*4
        calls = []
        def edge(length, reverse):
            curve = SimpleNamespace(GetLength3=mock.Mock(side_effect=lambda low,high: high-low))
            parameters = SimpleNamespace(UMinValue=-length/1000 if reverse else 0.0,
                UMaxValue=0.0 if reverse else length/1000,Sense=not reverse)
            return SimpleNamespace(GetCurve=lambda:(calls.append("curve"),curve)[1],
                GetCurveParams3=lambda:(calls.append("parameters"),parameters)[1]),curve
        pairs = [edge(value,index%2==1) for index,value in enumerate(expected)]
        reference = SimpleNamespace(GetSegmentCount=12,GetSegments=[pair[0] for pair in pairs])
        feature = SimpleNamespace(GetID=26,GetTypeName2="ImportedCurve",Name="Curve1",
            GetSpecificFeature2=reference,GetFirstSubFeature=None,GetNextSubFeature=None,GetNextFeature=None)
        document = SimpleNamespace(FirstFeature=feature,GetBodies2=lambda *args:())
        observed = module.read_wireframe(document,representation="reference-curves")
        self.assertEqual(observed["method"],"native-reference-curves")
        module.verify_wire_geometry(observed,"wireframe")
        self.assertEqual(calls,["curve","parameters"]*12)
        for value,(_,curve) in zip(expected,pairs):
            curve.GetLength3.assert_called_once_with(0.0,value/1000)
        # Neither native count mismatch nor a real nine-edge import is accepted.
        reference.GetSegmentCount = 13
        partial = {}
        with self.assertRaisesRegex(RuntimeError,"array differs"):
            module.read_wireframe(document,partial,representation="reference-curves")
        self.assertEqual(partial["feature_inventory"][0]["native_segment_count"],13)
        reference.GetSegmentCount = 9
        reference.GetSegments = reference.GetSegments[:9]
        with self.assertRaisesRegex(RuntimeError,"at least its twelve edges"):
            module.read_wireframe(document,partial,representation="reference-curves")
        self.assertEqual(partial["segment_count"],9)

    def test_curve_import_integer_setter_partial_failure_restores_without_retry(self):
        module = script("verify-step-export-calibration.py")
        codes={name:3000+index for index,name in enumerate(module.IMPORT_PROFILE)}
        codes.update(swImportCurvePreference=3003,
            swGeneralImportAs3dCurves=1,swGeneralImportAsSketches=0)
        values={3000:False,3001:True,3002:True,3003:0}
        writes=[]
        def setter(key,value):
            writes.append((key,value)); values[key]=value
            return value==0
        app=SimpleNamespace(GetDocumentCount=0,GetUserPreferenceToggle=lambda key:values[key],
            GetUserPreferenceIntegerValue=lambda key:values[key],SetUserPreferenceToggle=mock.Mock(),
            SetUserPreferenceIntegerValue=setter)
        evidence={}
        with self.assertRaisesRegex(RuntimeError,"unexpected observer import setter"):
            with module.observer_import_preferences(app,codes,lambda name,fn:fn(),evidence):
                self.fail("rejected setter must not import")
        self.assertEqual(writes,[(3003,1),(3003,0)])
        self.assertTrue(evidence["observer_import_preferences"]["restored"])
        self.assertEqual(values[3003],0)
        app.SetUserPreferenceToggle.assert_not_called()

    def test_legacy_import_profile_does_not_mistake_neutral_preference_for_general(self):
        module = script("verify-step-export-calibration.py")
        wanted={}
        with mock.patch.object(module,"_read_native_enum_constants",side_effect=lambda path,names:wanted.update(names) or {}) as resolve:
            module.read_import_constants("installed-swconst.tlb")
        self.assertEqual(wanted["swUserPreferenceIntegerValue_e"],{"swImportCurvePreference"})
        self.assertEqual(wanted["swGeneralImportFreePointCurveEntityOptions_e"],
                         {"swGeneralImportAs3dCurves","swGeneralImportAsSketches"})
        self.assertEqual(wanted["swUserPreferenceToggle_e"],
                         {"swMultiCAD_Enable3DInterconnect","swImportSolidSurface","swImportFreeCurves"})
        codes={name:4000+i for i,name in enumerate(module.IMPORT_PROFILE)}
        codes.update(swImportCurvePreference=4003,swGeneralImportAs3dCurves=1,swGeneralImportAsSketches=0)
        values={4000:False,4001:True,4002:True,4003:0,578:1}  # Neutral mode1 does not select General mode.
        writes=[]
        def setter(key,value):
            writes.append((key,value)); values[key]=value; return True
        app=SimpleNamespace(GetDocumentCount=0,GetUserPreferenceToggle=lambda key:values[key],
            GetUserPreferenceIntegerValue=lambda key:values[key],SetUserPreferenceToggle=mock.Mock(),
            SetUserPreferenceIntegerValue=setter)
        evidence={}
        with module.observer_import_preferences(app,codes,lambda name,fn:fn(),evidence):
            self.assertEqual(values[4003],1)
        self.assertEqual(writes,[(4003,1),(4003,0)])
        self.assertEqual(values[578],1)
        self.assertTrue(evidence["observer_import_preferences"]["restored"])

    def test_unexpected_sketch_type_rejection_retains_real_partial_geometry(self):
        module=script("verify-step-export-calibration.py")
        feature=SimpleNamespace(GetID=26,GetTypeName2="3DProfileFeature",Name="Sketch1",
            GetSpecificFeature2=SimpleNamespace(GetSketchSegments=[SimpleNamespace(GetLength=0.01)]*4),
            GetFirstSubFeature=None,GetNextSubFeature=None,GetNextFeature=None)
        document=SimpleNamespace(FirstFeature=feature,GetBodies2=lambda *args:())
        partial={}
        with self.assertRaisesRegex(RuntimeError,"unexpectedly produced sketch"):
            module.read_wireframe(document,partial,representation="reference-curves")
        self.assertEqual(partial["segment_count"],4)
        self.assertEqual(partial["total_length_mm"],40)
        self.assertFalse(partial["complete"])

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
        constants.update(swImportCurvePreference=1003,
            swGeneralImportAs3dCurves=1, swGeneralImportAsSketches=0)
        original = {1000: True, 1001: True, 1002: False, 1003: 0}
        values = dict(original)
        writes = []
        def setter(key, value):
            writes.append((key, value))
            values[key] = value
            return None
        app = SimpleNamespace(GetDocumentCount=0, GetUserPreferenceToggle=lambda key: values[key],
                              SetUserPreferenceToggle=setter, GetUserPreferenceIntegerValue=lambda key: values[key],
                              SetUserPreferenceIntegerValue=lambda key,value: (setter(key,value),True)[1])
        case = {}
        call = lambda name, function: function()
        with module.observer_import_preferences(app, constants, call, case):
            self.assertEqual(values, {**{constants[name]: value for name, value in module.IMPORT_PROFILE.items()},1003:1})
        self.assertEqual(values, original)
        self.assertTrue(case["observer_import_preferences"]["restored"])
        self.assertEqual(len(writes), 6)  # Two toggles plus the curve representation, once each way.
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
        constants.update(swImportCurvePreference=2003,
            swGeneralImportAs3dCurves=1, swGeneralImportAsSketches=0)
        values = {2000: True, 2001: True, 2002: False, 2003:0}
        app = SimpleNamespace(GetDocumentCount=0, GetUserPreferenceToggle=lambda key: values[key],
                              SetUserPreferenceToggle=lambda *args: None,
                              GetUserPreferenceIntegerValue=lambda key:values[key],
                              SetUserPreferenceIntegerValue=lambda *args:True)
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
